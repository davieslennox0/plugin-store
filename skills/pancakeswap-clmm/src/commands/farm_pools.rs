use crate::{config, rpc};
use std::sync::Arc;
use tokio::sync::Semaphore;

// Max concurrent RPC calls to avoid overwhelming public RPC endpoints
const MAX_CONCURRENT: usize = 25;

pub async fn run(chain_id: u64, rpc_url: Option<String>) -> anyhow::Result<()> {
    let cfg = config::get_chain_config(chain_id)?;
    let rpc = config::get_rpc_url(chain_id, rpc_url.as_deref())?;

    let length = rpc::pool_length(cfg.masterchef_v3, &rpc).await?;
    eprintln!(
        "Scanning {} pools on chain {} for active CAKE incentives...",
        length, chain_id
    );

    // Fetch all pools in parallel, capped at MAX_CONCURRENT to avoid RPC rate limits
    let semaphore = Arc::new(Semaphore::new(MAX_CONCURRENT));
    let handles: Vec<tokio::task::JoinHandle<(u64, anyhow::Result<rpc::PoolInfo>)>> = (0..length)
        .map(|pid| {
            let rpc_url = rpc.clone();
            let masterchef = cfg.masterchef_v3.to_string();
            let sem = Arc::clone(&semaphore);
            tokio::spawn(async move {
                let _permit = sem.acquire().await.unwrap();
                let result = rpc::pool_info(&masterchef, pid, &rpc_url).await;
                (pid, result)
            })
        })
        .collect();

    let mut active_pools = Vec::new();
    let mut failed = 0u64;
    for handle in handles {
        match handle.await {
            Ok((_, Ok(info))) if info.alloc_point > 0 => active_pools.push(info),
            Ok((_, Ok(_))) => {} // alloc_point == 0, inactive
            Ok((pid, Err(e))) => {
                eprintln!("  Warning: failed to fetch pool pid={}: {}", pid, e);
                failed += 1;
            }
            Err(e) => {
                eprintln!("  Warning: task join error: {}", e);
                failed += 1;
            }
        }
    }

    // Sort by alloc_point descending so highest-reward pools appear first
    active_pools.sort_by(|a, b| b.alloc_point.cmp(&a.alloc_point));

    let note = if failed > 0 {
        format!(
            "{} of {} pools have active CAKE incentives ({} fetch errors)",
            active_pools.len(),
            length,
            failed
        )
    } else {
        format!(
            "{} of {} pools have active CAKE incentives (alloc_point > 0), sorted by reward share",
            active_pools.len(),
            length
        )
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "ok": true,
            "chain_id": chain_id,
            "masterchef_v3": cfg.masterchef_v3,
            "total_pool_count": length,
            "active_pool_count": active_pools.len(),
            "note": note,
            "pools": active_pools
        }))?
    );
    Ok(())
}
