
# morpho -- Skill Summary

## Overview
The Morpho skill enables interaction with Morpho's permissionless lending protocol, which operates on two layers: Morpho Blue isolated lending markets and MetaMorpho ERC-4626 vaults curated by risk managers like Gauntlet and Steakhouse. Users can supply assets to earn yield, borrow against collateral, manage positions, and claim rewards across Ethereum Mainnet and Base networks with over $5B in total value locked.

## Usage
Install with `npx skills add okx/plugin-store-community --skill morpho`, ensure your wallet is connected via `onchainos wallet login`, then use commands like `morpho positions` to view your portfolio or `morpho markets --asset USDC` to browse lending opportunities. All write operations use dry-run simulation first and require explicit user confirmation before executing on-chain transactions.

## Commands
| Command | Description |
|---------|-------------|
| `morpho positions` | View your positions and health factors across Blue markets and MetaMorpho vaults |
| `morpho markets [--asset SYMBOL]` | List Morpho Blue markets with APYs, optionally filtered by asset |
| `morpho vaults [--asset SYMBOL]` | List MetaMorpho vaults with APYs and curators, optionally filtered by asset |
| `morpho supply --vault ADDR --asset SYMBOL --amount N` | Supply assets to a MetaMorpho vault |
| `morpho withdraw --vault ADDR --asset SYMBOL --amount N` | Withdraw from a MetaMorpho vault |
| `morpho borrow --market-id HEX --amount N` | Borrow from a Morpho Blue market |
| `morpho repay --market-id HEX --amount N` | Repay Morpho Blue debt |
| `morpho supply-collateral --market-id HEX --amount N` | Supply collateral to a Blue market |
| `morpho claim-rewards` | Claim Merkl rewards |

Global flags: `--chain CHAIN_ID` (1 for Ethereum, 8453 for Base), `--dry-run`, `--from ADDRESS`

## Triggers
Activate this skill when users mention lending, borrowing, or earning yield on Morpho, MetaMorpho vaults, Morpho Blue markets, health factors, or when they want to supply collateral, repay loans, or claim rewards on the Morpho protocol. Also trigger for phrases like "morpho positions", "metamorpho yield", or "borrow from morpho blue".
