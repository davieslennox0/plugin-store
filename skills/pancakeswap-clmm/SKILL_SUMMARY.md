
# pancakeswap-clmm -- Skill Summary

## Overview
This skill provides farming functionality for PancakeSwap V3 concentrated liquidity positions, allowing users to stake LP NFTs into MasterChefV3 contracts to earn CAKE rewards while collecting swap fees. It operates across BSC, Ethereum, Base, and Arbitrum networks and integrates with the onchainos wallet system for secure transaction execution.

## Usage
Install the plugin and use commands like `pancakeswap-clmm farm --token-id 12345` to stake LP NFTs or `pancakeswap-clmm harvest --token-id 12345` to claim rewards. All write operations require user confirmation before execution.

## Commands
| Command | Description |
|---------|-------------|
| `farm --token-id <ID>` | Stake LP NFT into MasterChefV3 to earn CAKE |
| `unfarm --token-id <ID>` | Withdraw staked NFT and harvest rewards |
| `harvest --token-id <ID>` | Claim pending CAKE rewards |
| `collect-fees --token-id <ID>` | Collect swap fees from unstaked position |
| `pending-rewards --token-id <ID>` | View pending CAKE rewards |
| `farm-pools` | List active farming pools |
| `positions` | View LP positions in wallet |

## Triggers
Activate this skill when users want to farm CAKE rewards with existing V3 LP positions, harvest accumulated rewards, or collect swap fees. Trigger phrases include "stake LP NFT", "farm CAKE", "harvest rewards", "collect fees", or "PancakeSwap farming".
