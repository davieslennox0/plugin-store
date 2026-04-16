# Changelog

## v0.2.5 — 2026-04-16

### Fixed

- **M1 — list-markets: impliedApy and liquidity always null**: Pendle API moved `impliedApy`
  and `liquidity` from top-level market fields into a nested `details` sub-object. The plugin
  now lifts both fields back to the top level when the top-level value is null, restoring
  correct APY and TVL display.

- **M2 — get-market: invalid time-frame values rejected by API**: The `--time-frame` flag
  accepted user-facing aliases `1D`, `1W`, `1M` but passed them raw to the Pendle API, which
  expects `hour`, `day`, `week` respectively. The plugin now maps the aliases before the API
  call.

## v0.2.4 — 2026-04-10

### Fixed

- Added global `--confirm` flag (required to broadcast any write transaction)
- Added global `--dry-run` flag (simulate without broadcasting)
- Balance pre-flight checks for all write commands
- `mint-py` and `redeem-py` now use Pendle v2 GET SDK endpoint (fixes classification errors)
- Added `get-market-info` command and `--market-id` alias
- Binary renamed from `pendle-plugin` to `pendle`
