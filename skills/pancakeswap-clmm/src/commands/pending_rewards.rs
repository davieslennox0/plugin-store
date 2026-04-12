use crate::{config, rpc};

pub async fn run(chain_id: u64, token_id: u64, rpc_url: Option<String>) -> anyhow::Result<()> {
    let cfg = config::get_chain_config(chain_id)?;
    let rpc = config::get_rpc_url(chain_id, rpc_url.as_deref())?;

    // Pre-check: verify token exists on-chain (ownerOf reverts for non-existent tokens)
    rpc::owner_of(cfg.nonfungible_position_manager, token_id, &rpc)
        .await
        .map_err(|_| {
            anyhow::anyhow!(
                "Token ID {} does not exist on chain {}.",
                token_id,
                chain_id
            )
        })?;

    let reward_wei = rpc::pending_cake(cfg.masterchef_v3, token_id, &rpc).await?;
    let reward_cake = rpc::format_cake_wei(reward_wei);

    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "ok": true,
            "chain_id": chain_id,
            "token_id": token_id,
            "pending_cake_wei": reward_wei.to_string(),
            "pending_cake": reward_cake,
            "masterchef_v3": cfg.masterchef_v3
        }))?
    );
    Ok(())
}
