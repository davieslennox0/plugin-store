/// `polymarket withdraw` — transfer USDC.e from proxy wallet back to EOA wallet.
///
/// Uses PROXY_FACTORY.proxy([op]) to execute a USDC.e transfer from the proxy's context.
/// The op encodes: transfer(eoa_address, amount) on the USDC.e contract.

use anyhow::{bail, Result};
use crate::onchainos::{get_usdc_balance, get_wallet_address};

pub async fn run(amount: &str, dry_run: bool) -> Result<()> {
    let eoa = get_wallet_address().await?;
    let creds = crate::config::load_credentials()
        .ok()
        .flatten()
        .ok_or_else(|| anyhow::anyhow!("No credentials found. Run `polymarket setup-proxy` first."))?;
    let proxy = creds.proxy_wallet
        .as_ref()
        .ok_or_else(|| anyhow::anyhow!("No proxy wallet configured. Run `polymarket setup-proxy` first."))?
        .clone();

    let amount_f: f64 = amount.parse().map_err(|_| anyhow::anyhow!("invalid amount"))?;
    if amount_f <= 0.0 {
        bail!("amount must be positive");
    }
    let amount_raw = (amount_f * 1_000_000.0).round() as u128;

    // Check proxy balance on-chain
    let proxy_bal = get_usdc_balance(&proxy).await?;
    let proxy_bal_raw = (proxy_bal * 1_000_000.0).floor() as u128;
    if proxy_bal_raw < amount_raw {
        bail!(
            "Insufficient proxy wallet balance: have ${:.2}, need ${:.2}",
            proxy_bal, amount_f
        );
    }

    if dry_run {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "ok": true,
            "dry_run": true,
            "data": {
                "from": proxy,
                "to": eoa,
                "token": "USDC.e",
                "amount": amount_f,
                "amount_raw": amount_raw,
                "note": "dry-run: no transaction submitted"
            }
        }))?);
        return Ok(());
    }

    eprintln!("[polymarket] Withdrawing ${:.2} USDC.e from proxy {} to EOA {}...", amount_f, proxy, eoa);
    let tx_hash = crate::onchainos::withdraw_usdc_from_proxy(&eoa, amount_raw).await?;
    eprintln!("[polymarket] Withdraw tx: {}", tx_hash);
    eprintln!("[polymarket] Waiting for confirmation...");
    crate::onchainos::wait_for_tx_receipt(&tx_hash, 30).await?;

    println!("{}", serde_json::to_string_pretty(&serde_json::json!({
        "ok": true,
        "data": {
            "tx_hash": tx_hash,
            "from": proxy,
            "to": eoa,
            "token": "USDC.e",
            "amount": amount_f,
        }
    }))?);
    Ok(())
}
