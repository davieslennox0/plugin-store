use serde_json::Value;

/// Call `onchainos wallet contract-call` and return parsed JSON output.
/// Set `confirm=true` to append `--force` and broadcast the transaction.
pub async fn wallet_contract_call(
    chain_id: u64,
    to: &str,
    input_data: &str,
    from: Option<&str>,
    amt: Option<u64>,
    dry_run: bool,
    confirm: bool,
) -> anyhow::Result<Value> {
    let chain_str = chain_id.to_string();
    let mut args = vec![
        "wallet",
        "contract-call",
        "--chain",
        &chain_str,
        "--to",
        to,
        "--input-data",
        input_data,
    ];
    let amt_str;
    if let Some(v) = amt {
        amt_str = v.to_string();
        args.extend_from_slice(&["--amt", &amt_str]);
    }
    let from_str;
    if let Some(f) = from {
        from_str = f.to_string();
        args.extend_from_slice(&["--from", &from_str]);
    }
    // In dry-run mode, just print the command that would be executed and return a simulated response.
    if dry_run {
        eprintln!("[morpho] [dry-run] Would run: onchainos {}", args.join(" "));
        return Ok(serde_json::json!({
            "ok": true,
            "data": {
                "txHash": "0x0000000000000000000000000000000000000000000000000000000000000000"
            }
        }));
    }

    if confirm {
        args.push("--force");
    }

    let output = tokio::process::Command::new("onchainos")
        .args(&args)
        .output()
        .await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(serde_json::from_str(&stdout)?)
}

/// Extract txHash from wallet contract-call response, returning an error if the call failed.
/// Response format: {"ok":true,"data":{"txHash":"0x..."}}
pub fn extract_tx_hash_or_err(result: &Value) -> anyhow::Result<String> {
    if result["ok"].as_bool() != Some(true) {
        let err_msg = result["error"].as_str()
            .or_else(|| result["message"].as_str())
            .unwrap_or("unknown error");
        return Err(anyhow::anyhow!("contract-call failed: {}", err_msg));
    }
    result["data"]["txHash"]
        .as_str()
        .or_else(|| result["txHash"].as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| anyhow::anyhow!("no txHash in contract-call response"))
}

/// Encode and submit an ERC-20 approve call.
/// Selector: 0x095ea7b3
pub async fn erc20_approve(
    chain_id: u64,
    token_addr: &str,
    spender: &str,
    amount: u128,
    from: Option<&str>,
    dry_run: bool,
    confirm: bool,
) -> anyhow::Result<Value> {
    // approve(address,uint256) selector = 0x095ea7b3
    let spender_clean = spender.trim_start_matches("0x");
    let spender_padded = format!("{:0>64}", spender_clean);
    let amount_hex = format!("{:064x}", amount);
    let calldata = format!("0x095ea7b3{}{}", spender_padded, amount_hex);
    wallet_contract_call(chain_id, token_addr, &calldata, from, None, dry_run, confirm).await
}

/// Query wallet balance (supports --output json).
pub async fn wallet_balance(chain_id: u64) -> anyhow::Result<Value> {
    let chain_str = chain_id.to_string();
    let output = tokio::process::Command::new("onchainos")
        .args(["wallet", "balance", "--chain", &chain_str, "--output", "json"])
        .output()
        .await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(serde_json::from_str(&stdout)?)
}

/// Query wallet status to get the active address.
pub async fn wallet_status() -> anyhow::Result<Value> {
    let output = tokio::process::Command::new("onchainos")
        .args(["wallet", "status", "--output", "json"])
        .output()
        .await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(serde_json::from_str(&stdout)?)
}

/// Resolve the caller's wallet address: use `from` if provided, otherwise
/// query the active onchainos wallet via `wallet addresses`.
pub async fn resolve_wallet(from: Option<&str>, _chain_id: u64) -> anyhow::Result<String> {
    if let Some(addr) = from {
        return Ok(addr.to_string());
    }
    let output = tokio::process::Command::new("onchainos")
        .args(["wallet", "addresses"])
        .output()
        .await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let v: Value = serde_json::from_str(&stdout)?;
    let addr = v["data"]["evmAddress"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("Could not determine active EVM wallet address. Ensure onchainos is logged in."))?
        .to_string();
    Ok(addr)
}
