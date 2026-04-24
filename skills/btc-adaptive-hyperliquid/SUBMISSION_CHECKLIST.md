# Submission Checklist

Copy into PR description and tick before submission:

- [ ] `plugin.yaml`, `.claude-plugin/plugin.json`, `SKILL.md`, and `SUMMARY.md` are present.
- [ ] `name` is lowercase, hyphenated, and below 40 characters.
- [ ] `version` matches in `plugin.yaml`, `plugin.json`, and `SKILL.md`.
- [ ] Replace `REPLACE_WITH_GITHUB_USERNAME` in `plugin.yaml` with your GitHub username.
- [ ] `LICENSE` is present.
- [ ] `api_calls` lists `fapi.binance.com` because the script can fetch public Binance futures data.
- [ ] `SKILL.md` includes Overview, Pre-flight, Commands, Error Handling, Security Notices.
- [ ] Trading risk disclaimer is present.
- [ ] Dry-run / paper-trade mode is the default.
- [ ] The script does not include private keys, seed phrases, API keys, or Telegram tokens.
- [ ] The script does not execute orders directly.
- [ ] Live execution instructions require Hyperliquid Plugin / Agentic Wallet.
- [ ] Local checks pass:
  - [ ] `python3 scripts/btc_adaptive_hyperliquid.py validate-config --config config/default.json`
  - [ ] `python3 scripts/btc_adaptive_hyperliquid.py demo --config config/default.json --output text`
  - [ ] `python3 -m unittest discover -s tests`
- [ ] If available, `plugin-store lint skills/btc-adaptive-hyperliquid` passes.
- [ ] PR title: `[new-plugin] btc-adaptive-hyperliquid v1.0.0`
- [ ] Branch: `submit/btc-adaptive-hyperliquid`
- [ ] PR only modifies files inside `skills/btc-adaptive-hyperliquid/`.
