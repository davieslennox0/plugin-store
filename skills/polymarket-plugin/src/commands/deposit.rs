/// `polymarket deposit` — transfer USDC.e to the proxy wallet.
///
/// Only applicable in POLY_PROXY mode. Sends an ERC-20 transfer from the
/// onchainos wallet to the proxy wallet address.
///
/// Prerequisites:
///   - `polymarket setup-proxy` must have been run first
///   - EOA wallet must hold enough USDC.e on Polygon (chain 137)

use anyhow::{bail, Result};
use reqwest::Client;

pub async fn run(amount: &str, dry_run: bool) -> Result<()> {
    let client = Client::new();

    let signer_addr = crate::onchainos::get_wallet_address().await?;
    let creds = crate::auth::ensure_credentials(&client, &signer_addr).await?;

    let proxy_wallet = creds.proxy_wallet.as_ref().ok_or_else(|| anyhow::anyhow!(
        "No proxy wallet configured. Run `polymarket setup-proxy` first."
    ))?;

    // Parse amount (human-readable USDC.e, 6 decimals).
    let amount_f: f64 = amount.parse()
        .map_err(|_| anyhow::anyhow!("invalid amount: {}", amount))?;
    if amount_f <= 0.0 {
        bail!("amount must be positive");
    }
    let amount_raw = (amount_f * 1_000_000.0).round() as u128;

    if dry_run {
        println!(
            "{}",
            serde_json::json!({
                "ok": true,
                "dry_run": true,
                "data": {
                    "from": signer_addr,
                    "to": proxy_wallet,
                    "token": "USDC.e",
                    "amount": amount_f,
                    "amount_raw": amount_raw,
                    "note": "dry-run: no transaction submitted"
                }
            })
        );
        return Ok(());
    }

    eprintln!("[polymarket] Transferring {} USDC.e to proxy wallet {}...", amount_f, proxy_wallet);
    let tx_hash = crate::onchainos::transfer_usdc_to_proxy(proxy_wallet, amount_raw).await?;

    println!(
        "{}",
        serde_json::json!({
            "ok": true,
            "data": {
                "tx_hash": tx_hash,
                "from": signer_addr,
                "to": proxy_wallet,
                "token": "USDC.e",
                "amount": amount_f,
                "note": "USDC.e deposited to proxy wallet. Ready to trade in POLY_PROXY mode."
            }
        })
    );
    Ok(())
}
