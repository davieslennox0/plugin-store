use clap::Args;
use crate::config::{info_url, exchange_url, now_ms, ARBITRUM_CHAIN_ID};
use crate::onchainos::{onchainos_hl_sign_withdraw, resolve_wallet_with_chain};
use crate::api::get_clearinghouse_state;
use crate::signing::submit_exchange_request;

#[derive(Args)]
pub struct WithdrawArgs {
    /// USDC amount to withdraw (e.g. 10 for $10 USDC)
    #[arg(long)]
    pub amount: f64,

    /// Destination address on Arbitrum (defaults to your wallet address)
    #[arg(long)]
    pub destination: Option<String>,

    /// Dry run — show payload without signing or submitting
    #[arg(long)]
    pub dry_run: bool,

    /// Confirm and submit (without this flag, shows a preview)
    #[arg(long)]
    pub confirm: bool,
}

pub async fn run(args: WithdrawArgs) -> anyhow::Result<()> {
    if args.amount <= 0.0 {
        anyhow::bail!("--amount must be positive (got {})", args.amount);
    }
    if args.amount < 2.0 {
        eprintln!("WARNING: Minimum withdrawal is $2 USDC. Amounts below $2 will be rejected by Hyperliquid.");
    }

    let info = info_url();
    let exchange = exchange_url();
    let nonce = now_ms();

    let (wallet, sign_chain_id) = resolve_wallet_with_chain(ARBITRUM_CHAIN_ID)?;
    let destination = args.destination.clone().unwrap_or_else(|| wallet.clone());

    // Format amount as string with up to 8 decimal places, trimming trailing zeros
    let amount_str = format!("{}", args.amount);

    // Fetch withdrawable balance
    let state = get_clearinghouse_state(info, &wallet).await?;
    let withdrawable: f64 = state["withdrawable"]
        .as_str().and_then(|s| s.parse().ok()).unwrap_or(0.0);

    if args.amount > withdrawable {
        anyhow::bail!(
            "Insufficient withdrawable balance: requested {:.6} USDC, available {:.6} USDC",
            args.amount, withdrawable
        );
    }

    if args.dry_run || !args.confirm {
        println!("{}", serde_json::json!({
            "ok": true,
            "preview": !args.confirm,
            "dry_run": args.dry_run,
            "action": "withdraw3",
            "wallet": wallet,
            "destination": destination,
            "amount_usd": args.amount,
            "withdrawable": format!("{:.6}", withdrawable),
            "note": if args.confirm { "" } else { "Add --confirm to execute. Funds arrive on Arbitrum in ~2-5 minutes." }
        }));
        return Ok(());
    }

    println!("Signing withdraw for {} USDC to {}...", args.amount, destination);
    let signed = onchainos_hl_sign_withdraw(&destination, &amount_str, nonce, &wallet, sign_chain_id)?;
    let result = submit_exchange_request(exchange, signed).await?;

    if result["status"].as_str() == Some("err") {
        anyhow::bail!("Withdraw failed: {}", result["response"].as_str().unwrap_or("unknown error"));
    }

    println!("{}", serde_json::json!({
        "ok": true,
        "action": "withdraw3",
        "wallet": wallet,
        "destination": destination,
        "amount_usd": args.amount,
        "result": result,
        "note": "USDC will arrive on Arbitrum in ~2-5 minutes."
    }));

    Ok(())
}
