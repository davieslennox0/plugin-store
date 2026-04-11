use clap::Args;
use serde_json::Value;

use crate::{api, config, onchainos};

#[derive(Args)]
pub struct PositionsArgs {
    /// Wallet address (optional; defaults to current onchainos Solana wallet)
    #[arg(long)]
    pub wallet: Option<String>,

    /// Market address (optional; defaults to main market)
    #[arg(long)]
    pub market: Option<String>,
}

/// Parse the `state.deposits` / `state.borrows` arrays into a compact list.
/// Filters out null-reserve slots (address = 111...1) and zero-amount entries.
/// `marketValueSf` is Kamino's Q64 fixed-point value; divide by 2^60 to get USD.
fn parse_state_positions(items: &[Value], reserve_key: &str, amount_key: &str) -> Vec<Value> {
    const NULL_RESERVE: &str = "11111111111111111111111111111111";
    items
        .iter()
        .filter(|item| {
            let reserve = item.get(reserve_key).and_then(|v| v.as_str()).unwrap_or("");
            reserve != NULL_RESERVE && !reserve.is_empty()
        })
        .filter(|item| {
            item.get(amount_key)
                .and_then(|v| v.as_str())
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(0)
                > 0
        })
        .map(|item| {
            let reserve = item.get(reserve_key).and_then(|v| v.as_str()).unwrap_or("");
            let symbol = crate::config::reserve_symbol(reserve);
            let raw_amount = item
                .get(amount_key)
                .and_then(|v| v.as_str())
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(0);
            let sf = item
                .get("marketValueSf")
                .and_then(|v| v.as_str())
                .and_then(|s| s.parse::<u128>().ok())
                .unwrap_or(0);
            // Use marketValueSf when available; fall back to raw_amount / 10^decimals
            // (accurate for stablecoins; approximate for volatile assets).
            let usd = if sf > 0 {
                format!("{:.6}", sf as f64 / (1u128 << 60) as f64)
            } else {
                let decimals = crate::config::reserve_decimals(reserve);
                format!("{:.6}", raw_amount as f64 / 10f64.powi(decimals as i32))
            };
            serde_json::json!({
                "token":       symbol,
                "reserve":     reserve,
                "amount_raw":  raw_amount.to_string(),
                "value_usd":   usd,
            })
        })
        .collect()
}

/// Extract only user-relevant fields from a raw obligation object.
/// Drops the `market` (full chain state) fields; reads deposits/borrows from `state`.
fn summarise_obligation(o: &Value) -> Value {
    let stats = o.get("refreshedStats").cloned().unwrap_or(Value::Null);
    let state = o.get("state").cloned().unwrap_or(Value::Null);

    let deposits = parse_state_positions(
        state.get("deposits").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]),
        "depositReserve",
        "depositedAmount",
    );
    let borrows = parse_state_positions(
        state.get("borrows").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]),
        "borrowReserve",
        "borrowedAmountOutsideElevationGroups",
    );

    serde_json::json!({
        "obligation": o.get("obligationAddress").and_then(|v| v.as_str()).unwrap_or(""),
        "tag": o.get("humanTag").and_then(|v| v.as_str()).unwrap_or(""),
        "deposits": deposits,
        "borrows":  borrows,
        "stats": {
            "net_value_usd":        stats.get("netAccountValue"),
            "total_deposit_usd":    stats.get("userTotalDeposit"),
            "total_borrow_usd":     stats.get("userTotalBorrow"),
            "loan_to_value":        stats.get("loanToValue"),
            "borrow_utilization":   stats.get("borrowUtilization"),
            "liquidation_ltv":      stats.get("liquidationLtv"),
        }
    })
}

pub async fn run(args: PositionsArgs) -> anyhow::Result<()> {
    let wallet = match args.wallet {
        Some(w) => w,
        None => onchainos::resolve_wallet_solana()?,
    };

    if wallet.is_empty() {
        anyhow::bail!("Cannot resolve wallet address. Pass --wallet or ensure onchainos is logged in.");
    }

    let market = args.market.as_deref().unwrap_or(config::MAIN_MARKET);

    let obligations = api::get_obligations(market, &wallet).await?;

    let result = if obligations.as_array().map(|a| a.is_empty()).unwrap_or(false) {
        serde_json::json!({
            "ok": true,
            "data": {
                "wallet": wallet,
                "market": market,
                "has_positions": false,
                "message": "No active positions found for this wallet on Kamino Lend",
                "obligations": []
            }
        })
    } else {
        let clean: Vec<Value> = obligations
            .as_array()
            .map(|arr| arr.iter().map(summarise_obligation).collect())
            .unwrap_or_default();

        serde_json::json!({
            "ok": true,
            "data": {
                "wallet": wallet,
                "market": market,
                "has_positions": true,
                "obligations": clean
            }
        })
    };

    println!("{}", serde_json::to_string_pretty(&result)?);
    Ok(())
}
