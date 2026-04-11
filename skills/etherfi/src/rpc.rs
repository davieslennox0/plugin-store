use anyhow::Context;
use serde_json::{json, Value};

/// Perform an eth_call via JSON-RPC.
pub async fn eth_call(to: &str, data: &str, rpc_url: &str) -> anyhow::Result<String> {
    let client = reqwest::Client::new();
    let body = json!({
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {"to": to, "data": data},
            "latest"
        ],
        "id": 1
    });
    let resp: Value = client
        .post(rpc_url)
        .json(&body)
        .send()
        .await
        .context("eth_call HTTP request failed")?
        .json()
        .await
        .context("eth_call JSON parse failed")?;
    if let Some(err) = resp.get("error") {
        anyhow::bail!("eth_call error: {}", err);
    }
    Ok(resp["result"].as_str().unwrap_or("0x").to_string())
}

/// Get ERC-20 balance.
/// balanceOf(address) -> uint256
/// Selector: 0x70a08231
pub async fn get_balance(token: &str, owner: &str, rpc_url: &str) -> anyhow::Result<u128> {
    let owner_padded = format!("{:0>64}", owner.trim_start_matches("0x"));
    let data = format!("0x70a08231{}", owner_padded);
    let hex = eth_call(token, &data, rpc_url).await?;
    let clean = hex.trim_start_matches("0x");
    let trimmed = if clean.len() > 32 { &clean[clean.len() - 32..] } else { clean };
    Ok(u128::from_str_radix(trimmed, 16).unwrap_or(0))
}

/// Get ERC-20 allowance.
/// allowance(address owner, address spender) -> uint256
/// Selector: 0xdd62ed3e
pub async fn get_allowance(
    token: &str,
    owner: &str,
    spender: &str,
    rpc_url: &str,
) -> anyhow::Result<u128> {
    let owner_padded = format!("{:0>64}", owner.trim_start_matches("0x"));
    let spender_padded = format!("{:0>64}", spender.trim_start_matches("0x"));
    let data = format!("0xdd62ed3e{}{}", owner_padded, spender_padded);
    let hex = eth_call(token, &data, rpc_url).await?;
    let clean = hex.trim_start_matches("0x");
    let trimmed = if clean.len() > 32 { &clean[clean.len() - 32..] } else { clean };
    Ok(u128::from_str_radix(trimmed, 16).unwrap_or(0))
}

/// weETH.convertToAssets(uint256 shares) -> uint256
/// Returns the amount of eETH equivalent for a given weETH shares amount.
/// Selector: 0x07a2d13a (keccak256("convertToAssets(uint256)")[0..4])
pub async fn weeth_convert_to_assets(
    weeth: &str,
    shares: u128,
    rpc_url: &str,
) -> anyhow::Result<u128> {
    let shares_hex = format!("{:0>64x}", shares);
    let data = format!("0x07a2d13a{}", shares_hex);
    let hex = eth_call(weeth, &data, rpc_url).await?;
    let clean = hex.trim_start_matches("0x");
    let trimmed = if clean.len() > 32 { &clean[clean.len() - 32..] } else { clean };
    Ok(u128::from_str_radix(trimmed, 16).unwrap_or(0))
}

/// weETH.getRate() -> uint256
/// Returns eETH per weETH exchange rate (18 decimals), e.g. 1.092e18 means 1 weETH = 1.092 eETH.
/// Selector: 0x679aefce (keccak256("getRate()")[0..4])
pub async fn weeth_get_rate(weeth: &str, rpc_url: &str) -> anyhow::Result<f64> {
    let hex = eth_call(weeth, "0x679aefce", rpc_url).await?;
    let clean = hex.trim_start_matches("0x");
    let trimmed = if clean.len() > 32 { &clean[clean.len() - 32..] } else { clean };
    let raw = u128::from_str_radix(trimmed, 16).unwrap_or(0);
    Ok(raw as f64 / 1e18)
}

/// WithdrawRequestNFT.isFinalized(uint256 tokenId) -> bool
/// Returns true if the withdrawal request has been finalized and ETH is ready to claim.
/// Selector: 0x33727c4d (keccak256("isFinalized(uint256)")[0..4])
pub async fn is_withdrawal_finalized(nft: &str, token_id: u64, rpc_url: &str) -> anyhow::Result<bool> {
    let data = format!("0x33727c4d{:0>64x}", token_id);
    let hex = eth_call(nft, &data, rpc_url).await?;
    let clean = hex.trim_start_matches("0x");
    // ABI bool: 32-byte value where last byte is 0x01 = true, 0x00 = false
    Ok(clean.ends_with('1'))
}

