use anyhow::Context;
use serde_json::{json, Value};

/// POST to the Hyperliquid info endpoint.
pub async fn info_post(url: &str, body: Value) -> anyhow::Result<Value> {
    let client = reqwest::Client::new();
    let resp = client
        .post(url)
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .context("Hyperliquid info HTTP request failed")?;

    let status = resp.status();
    let text = resp.text().await.context("Failed to read response body")?;

    if !status.is_success() {
        anyhow::bail!("Hyperliquid API error {}: {}", status, text);
    }

    serde_json::from_str(&text).context("Failed to parse Hyperliquid info response as JSON")
}

/// Get all mid prices: POST /info {"type":"allMids"}
/// Returns a map of coin -> mid price string, e.g. {"BTC":"67234.5","ETH":"3456.2",...}
pub async fn get_all_mids(info_url: &str) -> anyhow::Result<Value> {
    info_post(info_url, json!({"type": "allMids"})).await
}

/// Get clearinghouse state for a user (perp positions, margin summary).
/// POST /info {"type":"clearinghouseState","user":"0x..."}
pub async fn get_clearinghouse_state(info_url: &str, user: &str) -> anyhow::Result<Value> {
    info_post(
        info_url,
        json!({
            "type": "clearinghouseState",
            "user": user
        }),
    )
    .await
}

/// Get open orders for a user.
/// POST /info {"type":"openOrders","user":"0x..."}
pub async fn get_open_orders(info_url: &str, user: &str) -> anyhow::Result<Value> {
    info_post(
        info_url,
        json!({
            "type": "openOrders",
            "user": user
        }),
    )
    .await
}

/// Get metadata for all perpetual markets (asset index map, etc.).
/// POST /info {"type":"meta"}
pub async fn get_meta(info_url: &str) -> anyhow::Result<Value> {
    info_post(info_url, json!({"type": "meta"})).await
}

/// Look up the asset index for a coin symbol from meta.
/// Returns None if the coin is not found.
pub async fn get_asset_index(info_url: &str, coin: &str) -> anyhow::Result<usize> {
    let (idx, _) = get_asset_meta(info_url, coin).await?;
    Ok(idx)
}

/// Look up the asset index AND szDecimals for a coin symbol from meta.
pub async fn get_asset_meta(info_url: &str, coin: &str) -> anyhow::Result<(usize, u32)> {
    let meta = get_meta(info_url).await?;
    let universe = meta["universe"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("meta.universe missing or not an array"))?;

    let coin_upper = coin.to_uppercase();
    for (i, asset) in universe.iter().enumerate() {
        if let Some(name) = asset["name"].as_str() {
            if name.to_uppercase() == coin_upper {
                let sz_dec = asset["szDecimals"].as_u64().unwrap_or(4) as u32;
                return Ok((i, sz_dec));
            }
        }
    }
    anyhow::bail!("Coin '{}' not found in Hyperliquid universe", coin)
}

/// Get spot token + market metadata.
/// POST /info {"type":"spotMeta"}
pub async fn get_spot_meta(info_url: &str) -> anyhow::Result<Value> {
    info_post(info_url, json!({"type": "spotMeta"})).await
}

/// Get spot clearinghouse state for a user (spot balances).
/// POST /info {"type":"spotClearinghouseState","user":"0x..."}
pub async fn get_spot_clearinghouse_state(info_url: &str, user: &str) -> anyhow::Result<Value> {
    info_post(
        info_url,
        json!({
            "type": "spotClearinghouseState",
            "user": user
        }),
    )
    .await
}

/// Look up the spot asset index, market index, AND szDecimals for a token symbol.
/// Returns (asset_index, market_index, sz_decimals).
/// Spot asset index on HL = 10000 + spot market index.
pub async fn get_spot_asset_meta(info_url: &str, coin: &str) -> anyhow::Result<(usize, usize, u32)> {
    let meta = get_spot_meta(info_url).await?;
    let tokens = meta["tokens"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("spotMeta.tokens missing"))?;
    let universe = meta["universe"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("spotMeta.universe missing"))?;

    let coin_upper = coin.to_uppercase();

    // Find token index by name
    let tok_idx = tokens
        .iter()
        .find(|t| t["name"].as_str().map(|n| n.to_uppercase()) == Some(coin_upper.clone()))
        .and_then(|t| t["index"].as_u64())
        .ok_or_else(|| anyhow::anyhow!("Spot token '{}' not found", coin))? as usize;

    // Find market that has this token as base (first token in tokens array)
    let market = universe
        .iter()
        .find(|m| {
            m["tokens"]
                .as_array()
                .and_then(|t| t.first())
                .and_then(|v| v.as_u64())
                .map(|idx| idx as usize == tok_idx)
                .unwrap_or(false)
        })
        .ok_or_else(|| anyhow::anyhow!("No spot market for '{}'", coin))?;

    let mkt_idx = market["index"].as_u64().unwrap_or(0) as usize;
    let sz_decimals = tokens
        .iter()
        .find(|t| t["index"].as_u64().map(|i| i as usize) == Some(tok_idx))
        .and_then(|t| t["szDecimals"].as_u64())
        .unwrap_or(2) as u32;

    // Returns (asset_index, market_index, sz_decimals)
    // asset_index = 10000 + market_index (used in HL order actions for spot)
    Ok((10000 + mkt_idx, mkt_idx, sz_decimals))
}
