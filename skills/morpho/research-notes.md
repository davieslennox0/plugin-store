# Morpho Plugin — Research Notes

## Integration Path Chosen: API

No Rust SDK exists. All Morpho SDKs are TypeScript/JavaScript. The plugin will use:
- **Off-chain reads:** Morpho GraphQL API (`https://api.morpho.org/graphql`) — no auth required
- **On-chain writes:** Manual ABI encoding → `onchainos wallet contract-call --input-data <calldata>`
- **Reward claims:** Merkl API (`https://api.merkl.xyz/v4/claim`) for proof data, then on-chain claim call

---

## Key Architectural Decisions

### 1. Two distinct product layers

Morpho has two main interaction surfaces:

**Morpho Blue** — the isolated lending primitive:
- Direct borrow/supply/repay positions
- Every market is identified by a `MarketParams` struct `(loanToken, collateralToken, oracle, irm, lltv)`
- MarketId = `keccak256(abi.encode(marketParams))` — this is the `uniqueKey` in the GraphQL API
- All function calls require passing the full `MarketParams` struct, not just an id
- Same contract address on both Ethereum and Base: `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`

**MetaMorpho** — ERC-4626 vaults layered on top:
- Each vault is its own ERC-4626 contract deployed by curators (Gauntlet, Steakhouse, Moonwell, etc.)
- Standard `deposit(assets, receiver)` / `redeem(shares, receiver, owner)` interface
- Vault addresses differ per chain; resolve dynamically via GraphQL `vaultV2s` query
- MetaMorpho Factory v1.1: `0x1897A8997241C1cD4bD0698647e4EB7213535c24` (Ethereum), `0xFf62A7c278C62eD665133147129245053Bbf5918` (Base)

### 2. Same Morpho Blue address on all chains

`0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb` is deployed identically on Ethereum AND Base (deterministic CREATE2 deployment). This simplifies the implementation — no chain-specific address lookup for the core contract.

### 3. Reward system migrated to Merkl

As of 2024-2025, Morpho migrated ALL reward distributions (MORPHO token + third-party) from the original Universal Rewards Distributor (URD) to the Merkl stack. The claim flow is:
1. Call `GET https://api.merkl.xyz/v4/claim?user=<addr>&chainId=<id>`
2. Use the returned `tokens`, `amounts`, `proofs` to call `claim()` on the Merkl Distributor (`0x3Ef3D8bA38EBe18DB133cEc108f4D14CE00Dd9Ae` on mainnet)

The old URD contracts still exist but are not actively used for new rewards.

### 4. GraphQL API returns health factor directly

The `marketPositions` query returns `state.healthFactor` as a float — no need to compute it manually from oracle prices. This simplifies position monitoring significantly.

### 5. ERC-4626 V2 vaults — maxWithdraw quirk

MetaMorpho V2 vaults always return `0` for `maxWithdraw()` and `maxRedeem()`. To get the withdrawable amount, use `balanceOf(user)` and `convertToAssets(shares)` instead. The design doc notes this.

### 6. Full repayment — use shares, not assets

To fully repay a Morpho Blue position, the plugin should use `repay(marketParams, 0, borrowShares, onBehalf, 0x)` with `shares` mode rather than `assets` mode. Using `assets` can leave dust borrow shares due to interest accrual rounding. Get `borrowShares` from the `position()` view call or the GraphQL API.

### 7. ABI encoding complexity for Morpho Blue

The `supplyCollateral`, `borrow`, `repay`, and `withdraw` functions all take `MarketParams` as a memory struct followed by fixed params and (for `supply`/`repay`) a dynamic `bytes data` field. The dynamic bytes field is empty (`0x`) in normal usage, but ABI encoding still requires the offset and length words. The Developer Agent must implement proper ABI encoding for:
- Structs passed by value (5 × address/uint256)
- Dynamic `bytes` parameter (always empty = offset + length=0)
- Dynamic arrays for Merkl claim (tokens, amounts, proofs)

### 8. No community Skill to reference

No existing onchainos/plugin-store Morpho implementation was found. The Developer Agent starts from scratch. The closest architectural reference is an Aave plugin (if one exists in the store), since both are EVM lending protocols — but note the key difference: Aave uses a single Pool contract with asset-specific markets, while Morpho Blue uses isolated markets identified by the full MarketParams struct.

---

## Gotchas

1. **MarketParams must be fetched from API at runtime.** The oracle and irm addresses vary per market. Never hardcode MarketParams beyond the well-known addresses listed in design.md.

2. **lltv is in WAD (1e18).** 77% LLTV = `770000000000000000`. Ensure BigInt arithmetic everywhere.

3. **Oracle price scale is 1e36**, not 1e18. Morpho oracles return prices scaled to 1e36. Health factor manual computation must divide by 1e36.

4. **Vault V2 `maxWithdraw` returns 0.** Don't use it; use `balanceOf` + `convertToAssets`.

5. **Interest accrues between blocks.** When approving for repayment, add a small buffer (0.1–0.5%) to the approval amount to account for interest accrued between the approve and repay transactions.

6. **Position shares ≠ assets.** Both supply and borrow positions in Morpho Blue use internal share accounting. `borrowShares × totalBorrowAssets / totalBorrowShares = actual borrow amount`. The GraphQL API returns both `borrowShares` and `borrowAssets` (pre-computed), use the latter for display and the former for on-chain calls.

7. **GraphQL `uniqueKey` = bytes32 MarketId.** When calling `position(id, user)` or `market(id)` directly via RPC, use the `uniqueKey` from the API as the bytes32 parameter (as a hex string with 0x prefix).
