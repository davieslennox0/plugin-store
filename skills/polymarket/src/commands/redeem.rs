use anyhow::{bail, Result};
use reqwest::Client;

use crate::api::{get_clob_market, get_gamma_market_by_slug};
use crate::onchainos::ctf_redeem_positions;

/// Run the redeem command.
///
/// market_id: condition_id (0x-prefixed) or slug
/// dry_run: if true, print preview and exit without submitting the tx
pub async fn run(market_id: &str, dry_run: bool) -> Result<()> {
    let client = Client::new();

    // Resolve condition_id and check neg_risk
    let (condition_id, neg_risk, question) = if market_id.starts_with("0x") {
        let m = get_clob_market(&client, market_id).await?;
        let q = m.question.unwrap_or_default();
        (m.condition_id, m.neg_risk, q)
    } else {
        let m = get_gamma_market_by_slug(&client, market_id).await?;
        let cid = m
            .condition_id
            .ok_or_else(|| anyhow::anyhow!("market has no conditionId: {}", market_id))?;
        let q = m.question.unwrap_or_default();
        (cid, m.neg_risk, q)
    };

    if neg_risk {
        bail!(
            "redeem is not supported for neg_risk (multi-outcome) markets — use the Polymarket web UI to redeem positions in this market"
        );
    }

    let cid_hex = condition_id.trim_start_matches("0x");
    let cid_display = format!("0x{}", cid_hex);

    if dry_run {
        let out = serde_json::json!({
            "ok": true,
            "data": {
                "dry_run": true,
                "market_id": market_id,
                "condition_id": cid_display,
                "question": question,
                "neg_risk": false,
                "action": "redeemPositions",
                "index_sets": [1, 2],
                "note": "dry-run: CTF redeemPositions tx not submitted. index_sets [1,2] covers YES and NO outcomes — the CTF contract pays out winning tokens and silently no-ops for losing ones."
            }
        });
        println!("{}", serde_json::to_string_pretty(&out)?);
        return Ok(());
    }

    let tx_hash = ctf_redeem_positions(&condition_id).await?;

    let out = serde_json::json!({
        "ok": true,
        "data": {
            "condition_id": cid_display,
            "question": question,
            "tx_hash": tx_hash,
            "note": "redeemPositions submitted. USDC.e will be transferred to your wallet once the tx confirms on Polygon."
        }
    });
    println!("{}", serde_json::to_string_pretty(&out)?);
    Ok(())
}
