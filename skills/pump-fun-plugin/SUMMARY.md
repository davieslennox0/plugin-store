**Overview**

Buy and sell tokens on pump.fun bonding curves from the CLI — check token info, bonding curve progress, and price quotes before any on-chain action.

**Prerequisites**
- onchainos agentic wallet connected with a Solana wallet (chain 501)
- At least 0.05 SOL in your wallet (covers a small buy plus network fees)
- A pump.fun token mint address — active bonding curve tokens end in `pump`

**How it Works**
1. **Check wallet readiness**: Verify your wallet is connected and has enough SOL. `pump-fun-plugin quickstart`
2. **Research a token**: See bonding curve reserves, current price, and graduation progress. `pump-fun-plugin get-token-info --mint <TOKEN_MINT>`
3. **Get a price quote**: Check the expected cost before buying or expected proceeds before selling. `pump-fun-plugin get-price --mint <TOKEN_MINT> --direction buy`
4. **Preview a buy**: See the transaction details without sending — no gas. `pump-fun-plugin buy --mint <TOKEN_MINT> --sol-amount <amount>`
5. **Execute the buy**: Purchase tokens from the bonding curve. `pump-fun-plugin buy --mint <TOKEN_MINT> --sol-amount <amount> --confirm`
6. **Preview a sell**: See expected SOL proceeds before selling. `pump-fun-plugin sell --mint <TOKEN_MINT> --token-amount <AMOUNT>`
7. **Execute the sell**: Sell tokens back to the bonding curve — omit `--token-amount` to sell your full balance. `pump-fun-plugin sell --mint <TOKEN_MINT> --token-amount <AMOUNT> --confirm`
