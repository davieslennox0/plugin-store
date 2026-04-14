use clap::Args;
use reqwest::Client;
use serde_json::json;

use crate::onchainos;
use crate::solana_rpc;

const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

#[derive(Args, Debug)]
pub struct QuickstartArgs {
    /// Meteora DLMM pool address to inspect
    #[arg(long)]
    pub pool: String,

    /// Wallet address. If omitted, uses the currently logged-in onchainos wallet.
    #[arg(long)]
    pub wallet: Option<String>,
}

pub async fn execute(args: &QuickstartArgs) -> anyhow::Result<()> {
    let client = Client::new();

    // ── 1. Resolve wallet ────────────────────────────────────────────────────
    let wallet_str = if let Some(w) = &args.wallet {
        w.clone()
    } else {
        onchainos::resolve_wallet_solana().map_err(|e| {
            anyhow::anyhow!("Cannot resolve wallet. Pass --wallet or log in via onchainos.\nError: {e}")
        })?
    };

    // ── 2. Fetch pool data ───────────────────────────────────────────────────
    let pool_data = solana_rpc::get_account_data(&client, &args.pool)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to fetch pool {}: {e}", args.pool))?;
    let pool = solana_rpc::parse_lb_pair(&pool_data)
        .map_err(|e| anyhow::anyhow!("Failed to parse LbPair: {e}"))?;

    let active_id = pool.active_id;
    let bin_step = pool.bin_step;

    // Approximate price: each bin covers bin_step / 100 % price change
    // price ~ (1 + bin_step/10000)^active_id relative to some base
    // For SOL/USDC with bin_step=4 bps, we estimate from active_id
    // Price = 1.0004^active_id (base = 1 USDC per SOL unit at id=0)
    // This is a rough approximation useful for orientation only.
    let price_approx = (1.0_f64 + bin_step as f64 / 10000.0).powi(active_id);

    // ── 3. Fetch balances ────────────────────────────────────────────────────
    let sol_balance = onchainos::get_sol_balance(&wallet_str);
    let usdc_balance = onchainos::get_spl_token_balance(USDC_MINT);

    // ── 4. Build suggestion ──────────────────────────────────────────────────
    let has_sol = sol_balance >= 0.01;   // enough for gas (0.01) + min deposit (0.001)
    let has_usdc = usdc_balance >= 1.0;  // enough for Y-only deposit

    let (mode, reason, command) = match (has_sol, has_usdc) {
        (true, true) => (
            "two_sided",
            "You have both SOL and USDC — deposit both for maximum fee earning range",
            format!(
                "meteora-plugin add-liquidity --pool {} --amount-x 0.001 --amount-y 0.5",
                args.pool
            ),
        ),
        (true, false) => (
            "x_only",
            "You have SOL but little USDC — do an X-only SOL deposit above the active bin",
            format!(
                "meteora-plugin add-liquidity --pool {} --amount-x 0.001",
                args.pool
            ),
        ),
        (false, true) => (
            "y_only",
            "You have USDC but little SOL — do a Y-only USDC deposit below the active bin",
            format!(
                "meteora-plugin add-liquidity --pool {} --amount-y 0.5",
                args.pool
            ),
        ),
        (false, false) => (
            "insufficient_funds",
            "Insufficient balance. You need at least 0.01 SOL (for gas + deposit) or 1.0 USDC to deposit",
            format!(
                "# Fund your wallet first, then run:\nmeteora-plugin add-liquidity --pool {}",
                args.pool
            ),
        ),
    };

    let output = json!({
        "ok": true,
        "wallet": wallet_str,
        "sol_balance": sol_balance,
        "usdc_balance": usdc_balance,
        "pool": args.pool,
        "active_id": active_id,
        "bin_step": bin_step,
        "price_approx": price_approx,
        "suggestion": {
            "mode": mode,
            "reason": reason,
            "command": command
        }
    });
    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}
