---
name: go-sol-price
description: Query the current SOL/USDT spot price from OKX's public ticker API. Trigger when the user asks "SOL price", "Solana price", "查 SOL 价格", or wants a quick on-demand spot quote without an API key.
version: "1.0.0"
---


## Pre-flight Dependencies (auto-injected by Plugin Store CI)

> Run once per session before first use. These checks ensure required tools are installed.

### Version check (auto-injected)

> **AI Agent Instruction**: Run this version check before executing any commands from this skill. If an update is applied, re-read this SKILL.md before proceeding — the instructions may have changed.

```bash
# Check for skill updates (1-hour cache)
UPDATE_CACHE="$HOME/.plugin-store/update-cache/go-sol-price"
CACHE_MAX=3600
LOCAL_VER="1.0.0"
DO_CHECK=true

if [ -f "$UPDATE_CACHE" ]; then
  CACHE_MOD=$(stat -f %m "$UPDATE_CACHE" 2>/dev/null || stat -c %Y "$UPDATE_CACHE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE=$(( NOW - CACHE_MOD ))
  [ "$AGE" -lt "$CACHE_MAX" ] && DO_CHECK=false
fi

if [ "$DO_CHECK" = true ]; then
  REMOTE_VER=$(curl -sf --max-time 3 "https://raw.githubusercontent.com/okx/plugin-store/main/skills/go-sol-price/plugin.yaml" | grep '^version' | head -1 | tr -d '"' | awk '{print $2}')
  if [ -n "$REMOTE_VER" ]; then
    mkdir -p "$HOME/.plugin-store/update-cache"
    echo "$REMOTE_VER" > "$UPDATE_CACHE"
  fi
fi

REMOTE_VER=$(cat "$UPDATE_CACHE" 2>/dev/null || echo "$LOCAL_VER")
if [ "$REMOTE_VER" != "$LOCAL_VER" ]; then
  echo "Update available: go-sol-price v$LOCAL_VER -> v$REMOTE_VER. Updating..."
  npx skills add okx/plugin-store --skill go-sol-price --yes --global 2>/dev/null || true
  echo "Updated go-sol-price to v$REMOTE_VER. Please re-read this SKILL.md."
fi
```

### Install go-sol-price binary + launcher (auto-injected)

```bash
# Install shared infrastructure (launcher + update checker, only once)
LAUNCHER="$HOME/.plugin-store/launcher.sh"
CHECKER="$HOME/.plugin-store/update-checker.py"
if [ ! -f "$LAUNCHER" ]; then
  mkdir -p "$HOME/.plugin-store"
  curl -fsSL "https://raw.githubusercontent.com/okx/plugin-store/main/scripts/launcher.sh" -o "$LAUNCHER" 2>/dev/null || true
  chmod +x "$LAUNCHER"
fi
if [ ! -f "$CHECKER" ]; then
  curl -fsSL "https://raw.githubusercontent.com/okx/plugin-store/main/scripts/update-checker.py" -o "$CHECKER" 2>/dev/null || true
fi

# Clean up old installation
rm -f "$HOME/.local/bin/go-sol-price" "$HOME/.local/bin/.go-sol-price-core" 2>/dev/null

# Download binary
OS=$(uname -s | tr A-Z a-z)
ARCH=$(uname -m)
EXT=""
case "${OS}_${ARCH}" in
  darwin_arm64)  TARGET="aarch64-apple-darwin" ;;
  darwin_x86_64) TARGET="x86_64-apple-darwin" ;;
  linux_x86_64)  TARGET="x86_64-unknown-linux-musl" ;;
  linux_i686)    TARGET="i686-unknown-linux-musl" ;;
  linux_aarch64) TARGET="aarch64-unknown-linux-musl" ;;
  linux_armv7l)  TARGET="armv7-unknown-linux-musleabihf" ;;
  mingw*_x86_64|msys*_x86_64|cygwin*_x86_64)   TARGET="x86_64-pc-windows-msvc"; EXT=".exe" ;;
  mingw*_i686|msys*_i686|cygwin*_i686)           TARGET="i686-pc-windows-msvc"; EXT=".exe" ;;
  mingw*_aarch64|msys*_aarch64|cygwin*_aarch64)  TARGET="aarch64-pc-windows-msvc"; EXT=".exe" ;;
esac
mkdir -p ~/.local/bin
curl -fsSL "https://github.com/okx/plugin-store/releases/download/plugins/go-sol-price@1.0.0/go-sol-price-${TARGET}${EXT}" -o ~/.local/bin/.go-sol-price-core${EXT}
chmod +x ~/.local/bin/.go-sol-price-core${EXT}

# Symlink CLI name to universal launcher
ln -sf "$LAUNCHER" ~/.local/bin/go-sol-price

# Register version
mkdir -p "$HOME/.plugin-store/managed"
echo "1.0.0" > "$HOME/.plugin-store/managed/go-sol-price"
```

---


# go-sol-price

A minimal Go CLI that prints the current `SOL/USDT` spot price by hitting OKX's public ticker endpoint. No API key, no third-party Go dependencies — single self-contained binary, ~3 MB.

## When to use

Say one of these to trigger:
- "what's the SOL price"
- "Solana current price"
- "查 SOL 现价"
- "SOL/USDT 报价"

## Usage

```bash
go-sol-price                # → SOL/USDT: 178.42
go-sol-price --version      # → go-sol-price 1.0.0
go-sol-price --help
```

## How it works

Single `GET https://www.okx.com/api/v5/market/ticker?instId=SOL-USDT`, parses `data[0].last`, prints. 10-second timeout, exits non-zero on network or API error.

## Limitations

- Read-only — no trading, no signing, no on-chain action
- Single instrument hardcoded (`SOL-USDT`) — extend to other pairs if needed
- Public endpoint, no auth, subject to OKX rate limits (generous for public API)
