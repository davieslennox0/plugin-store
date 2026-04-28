## Overview

`go-sol-price` is a tiny Go CLI that queries the OKX public spot ticker for `SOL-USDT` and prints the current price. No API key required, no third-party Go dependencies — a single self-contained binary you can drop in your `$PATH`.

## Prerequisites
- Network access to `https://www.okx.com/api/v5/market/ticker`
- Go is **not** required at runtime — the published release ships the compiled binary for your platform

## Quick Start
1. Install the skill: `npx skills add okx/plugin-store --skill go-sol-price`
2. Verify the binary: `go-sol-price --version` → `go-sol-price 1.0.0`
3. Query the price: `go-sol-price` → e.g. `SOL/USDT: 178.42`
4. Build locally (optional): `go build -o go-sol-price ./...`
