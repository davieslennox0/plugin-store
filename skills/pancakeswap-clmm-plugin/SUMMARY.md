**Overview**

Stake PancakeSwap V3 LP NFTs into MasterChefV3 to earn CAKE rewards on top of swap fees — with harvest, unfarm, and collect-fees commands across BSC, Ethereum, Base, and Arbitrum.

**Prerequisites**
- onchainos agentic wallet connected
- A PancakeSwap V3 LP NFT (create one with `pancakeswap-v3-plugin`)
- Some BNB in your wallet for gas

**How it Works**
1. **Get an LP NFT** (skip if you already have one):
   - 1.1 **Find a pool**: Look up available fee tiers for your token pair — `pancakeswap-v3-plugin pools --token-a CAKE --token-b BNB`
   - 1.2 **Mint the LP position**: Provide liquidity to receive an LP NFT — note the token ID in the output. `pancakeswap-v3-plugin add-liquidity --token-a CAKE --token-b BNB --fee 2500 --amount-a <amount-a> --amount-b <amount-b> --confirm`
2. **Check existing positions**: See all your V3 LP NFTs — both staked and unstaked. `pancakeswap-clmm-plugin positions`
3. **Browse farming pools**: Find pools with active CAKE emissions and their allocation points. `pancakeswap-clmm-plugin farm-pools`
4. **Stake the NFT**: Deposit your LP NFT into MasterChefV3 to start earning CAKE — preview first, add `--confirm` to execute. `pancakeswap-clmm-plugin farm --token-id <TOKEN_ID> --confirm`
5. **Check pending rewards**: See how much CAKE has accrued since staking. `pancakeswap-clmm-plugin pending-rewards --token-id <TOKEN_ID>`
6. **Harvest CAKE**: Claim rewards without withdrawing your LP position. `pancakeswap-clmm-plugin harvest --token-id <TOKEN_ID> --confirm`
7. **Stop farming**: Withdraw the NFT and harvest all remaining CAKE in one transaction. `pancakeswap-clmm-plugin unfarm --token-id <TOKEN_ID> --confirm`
