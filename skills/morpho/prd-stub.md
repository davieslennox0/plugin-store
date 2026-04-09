# Morpho — Plugin Store 接入 PRD

> 通过 onchainos CLI 接入 Morpho，使 AI Agent 能完成借贷操作

---

## 0. Plugin Meta

| Field | Value |
|-------|-------|
| plugin_name | `morpho` |
| dapp_name | Morpho |
| dapp_repo | https://github.com/morpho-org/morpho-blue |
| dapp_alias | morpho blue, morpho protocol, morpho v1 |
| one_liner | Supply, borrow and earn yield on Morpho — a permissionless lending protocol with $3B+ TVL |
| category | defi-protocol |
| tags | lending, borrowing, defi, earn, morpho, collateral |
| target_chains | ethereum (1), base (8453) |
| target_protocols | Morpho Blue |

---

## 1. Background

### 这个 DApp 是什么

Morpho is a permissionless lending protocol. Morpho Blue is the core protocol — it allows creating isolated lending markets with any asset. MetaMorpho vaults sit on top and aggregate liquidity. $3B+ TVL. Core operations: supply to vault, withdraw, borrow from market, repay.

### 接入可行性调研

> Researcher Agent: please complete this table

| 检查项 | 结果 |
|--------|------|
| 有 Rust SDK？ | TBD |
| SDK 支持哪些技术栈？ | TBD |
| 有 REST API？ | TBD (https://api.morpho.org likely exists) |
| 有官方 Skill？ | TBD |
| 开源社区有类似 Skill？ | TBD |
| 支持哪些链？ | Ethereum (1), Base (8453) |
| 是否需要 onchainos 广播？ | Yes |

### 接入路径判定

TBD — Researcher Agent to determine. Expected: API path since no Rust SDK is known.

---

## 2. Interface Mapping

> Researcher Agent: please complete §2–§5

### Operations to support (at minimum)

| # | Operation | Type | Priority |
|---|-----------|------|----------|
| 1 | Supply to MetaMorpho vault | On-chain | P0 |
| 2 | Withdraw from vault | On-chain | P0 |
| 3 | Borrow from Morpho Blue market | On-chain | P0 |
| 4 | Repay debt | On-chain | P0 |
| 5 | View positions / health | Off-chain read | P0 |
| 6 | List markets / APYs | Off-chain read | P0 |
| 7 | Claim rewards | On-chain | P1 |

---

## 3. User Scenarios

> Researcher Agent: please write at least 3 complete scenarios

---

## 4. External API Dependencies

> Researcher Agent: to complete
> Expected: https://api.morpho.org (GraphQL or REST)

---

## 5. Configuration Parameters

> Researcher Agent: to complete

| Parameter | Default | Description |
|-----------|---------|-------------|
| chain | 1 (Ethereum) | Target chain ID |
| dry_run | false | Simulate without broadcasting |
