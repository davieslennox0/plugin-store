# BTC Adaptive Hyperliquid

An advanced BTC perpetual strategy planner for Plugin Store DApp Challenge submissions. It is built to sit on top of the Hyperliquid Plugin: this repository generates strategy plans; the Hyperliquid Plugin handles account reads and any live execution.

## Why this design

The challenge requires Strategy Skills to be built on top of Polymarket Plugin or Hyperliquid Plugin. This Skill therefore avoids direct Hyperliquid API execution and keeps all live trading actions in the Hyperliquid Plugin / Agentic Wallet path.

## Project layout

```text
skills/btc-adaptive-hyperliquid/
├── .claude-plugin/plugin.json
├── plugin.yaml
├── SKILL.md
├── SUMMARY.md
├── README.md
├── LICENSE
├── config/default.json
├── scripts/btc_adaptive_hyperliquid.py
├── examples/
├── references/
└── tests/
```

## Local checks

From the plugin directory:

```bash
python3 scripts/btc_adaptive_hyperliquid.py validate-config --config config/default.json
python3 scripts/btc_adaptive_hyperliquid.py demo --config config/default.json --output text
python3 -m unittest discover -s tests
```

If the Plugin Store CLI is installed:

```bash
plugin-store lint skills/btc-adaptive-hyperliquid
```

## Submission notes

Before opening a PR, replace `REPLACE_WITH_GITHUB_USERNAME` in `plugin.yaml` with your GitHub username.

Suggested PR title:

```text
[new-plugin] btc-adaptive-hyperliquid v1.0.0
```

Suggested branch:

```text
submit/btc-adaptive-hyperliquid
```

## License

MIT.
