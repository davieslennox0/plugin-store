// commands/get_balances.rs — Query user LP token balances across Curve pools via Multicall3
use crate::{api, config, onchainos, rpc};
use anyhow::Result;

/// Max pools per Multicall3 batch (~88 KB calldata each, safe for public nodes).
const BATCH_SIZE: usize = 200;

/// Minimum LP balance to show — filters out Curve's 1-wei and 64-wei pool
/// initialization seeds that appear as "positions" for every factory pool.
/// Any real deposit produces orders of magnitude more LP tokens than this.
const MIN_LP_BALANCE: u128 = 1_000_000;

pub async fn run(chain_id: u64, wallet: Option<String>) -> Result<()> {
    let chain_name = config::chain_name(chain_id);
    let rpc_url = config::rpc_url(chain_id);

    // Resolve wallet address
    let wallet_addr = match wallet {
        Some(w) => w,
        None => {
            let w = onchainos::resolve_wallet(chain_id)?;
            if w.is_empty() {
                anyhow::bail!(
                    "Cannot determine wallet address. Pass --wallet or ensure onchainos is logged in."
                );
            }
            w
        }
    };

    // Fetch all pools from Curve API
    let pools = api::get_all_pools(chain_name).await?;
    // For older Curve v1 pools, the LP token is a separate contract (lpTokenAddress).
    // For factory/crypto pools the LP token IS the pool address.
    let lp_addrs: Vec<&str> = pools
        .iter()
        .map(|p| {
            p.lp_token_address
                .as_deref()
                .filter(|s| !s.is_empty())
                .unwrap_or(&p.address)
        })
        .collect();

    // Batch balanceOf via Multicall3: N sequential calls → ceil(N/200) calls
    let mut all_balances: Vec<u128> = Vec::with_capacity(pools.len());
    for chunk in lp_addrs.chunks(BATCH_SIZE) {
        let balances = rpc::multicall_balance_of(chunk, &wallet_addr, rpc_url)
            .await
            .unwrap_or_else(|_| vec![0u128; chunk.len()]);
        all_balances.extend(balances);
    }

    // Collect pools where LP balance > 0
    let mut positions = Vec::new();
    for (pool, balance) in pools.iter().zip(all_balances.iter()) {
        if *balance >= MIN_LP_BALANCE {
            let coins: Vec<_> = pool.coins.iter().map(|c| c.symbol.as_str()).collect();
            // All Curve LP tokens use 18 decimals
            let lp_human = format!("{:.6}", *balance as f64 / 1e18);
            positions.push(serde_json::json!({
                "pool_id": pool.id,
                "pool_name": pool.name,
                "pool_address": pool.address,
                "coins": coins,
                "lp_balance": lp_human,
                "lp_balance_raw": balance.to_string(),
                "tvl_usd": pool.usd_total
            }));
        }
    }

    println!(
        "{}",
        serde_json::json!({
            "ok": true,
            "wallet": wallet_addr,
            "chain": chain_name,
            "positions_count": positions.len(),
            "positions": positions
        })
    );
    Ok(())
}
