use anyhow::Result;
use crate::onchainos::{get_pol_balance, get_usdc_balance, get_wallet_address};

/// Truncate a contract address to "0xABCD...xyz789" format (first 4 + last 6 hex chars).
fn short_addr(addr: &str) -> String {
    let hex = addr.trim_start_matches("0x");
    if hex.len() <= 10 {
        return addr.to_string();
    }
    format!("0x{}...{}", &hex[..4], &hex[hex.len() - 6..])
}

pub async fn run() -> Result<()> {
    let eoa = get_wallet_address().await?;
    let proxy = crate::config::load_credentials()
        .ok()
        .flatten()
        .and_then(|c| c.proxy_wallet);

    let usdc_e_contract = crate::config::Contracts::USDC_E;
    let usdc_e_short = short_addr(usdc_e_contract);

    // Fetch EOA balances (POL + USDC.e) in parallel
    let (pol_result, usdc_result) = tokio::join!(
        get_pol_balance(&eoa),
        get_usdc_balance(&eoa),
    );

    let eoa_pol = match pol_result {
        Ok(v)  => format!("{:.4} POL", v),
        Err(e) => format!("error: {}", e),
    };
    let eoa_usdc = match usdc_result {
        Ok(v)  => format!("${:.2}", v),
        Err(e) => format!("error: {}", e),
    };

    let mut data = serde_json::json!({
        "eoa_wallet": {
            "address": eoa,
            "pol": eoa_pol,
            "usdc_e": eoa_usdc,
            "usdc_e_contract": usdc_e_short,
        }
    });

    // If proxy wallet is initialized, fetch its balances too
    if let Some(ref proxy_addr) = proxy {
        let (proxy_pol_result, proxy_usdc_result) = tokio::join!(
            get_pol_balance(proxy_addr),
            get_usdc_balance(proxy_addr),
        );
        let proxy_pol = match proxy_pol_result {
            Ok(v)  => format!("{:.4} POL", v),
            Err(e) => format!("error: {}", e),
        };
        let proxy_usdc = match proxy_usdc_result {
            Ok(v)  => format!("${:.2}", v),
            Err(e) => format!("error: {}", e),
        };
        data["proxy_wallet"] = serde_json::json!({
            "address": proxy_addr,
            "pol": proxy_pol,
            "usdc_e": proxy_usdc,
            "usdc_e_contract": usdc_e_short,
        });
    }

    println!("{}", serde_json::to_string_pretty(&serde_json::json!({
        "ok": true,
        "data": data,
    }))?);
    Ok(())
}
