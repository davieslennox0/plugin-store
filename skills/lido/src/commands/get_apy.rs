use crate::config;

pub async fn run() -> anyhow::Result<()> {
    let url = format!("{}/v1/protocol/steth/apr/sma", config::API_BASE_URL);

    let client = reqwest::Client::new();
    let resp = client
        .get(&url)
        .header("User-Agent", "Mozilla/5.0 (compatible; lido-plugin/0.1)")
        .header("Accept", "application/json")
        .send()
        .await?;

    // Fallback: /apr/sma was deprecated on some edge nodes; try /apr/last
    let body: serde_json::Value = if resp.status().is_success() {
        resp.json().await?
    } else {
        let fallback_url = format!("{}/v1/protocol/steth/apr/last", config::API_BASE_URL);
        let resp2 = client
            .get(&fallback_url)
            .header("User-Agent", "Mozilla/5.0 (compatible; lido-plugin/0.1)")
            .header("Accept", "application/json")
            .send()
            .await?;
        if !resp2.status().is_success() {
            anyhow::bail!("Failed to fetch APR: HTTP {}", resp2.status());
        }
        resp2.json().await?
    };

    // Try to extract APR from various response shapes
    let apr = extract_apr(&body);

    println!("=== Lido stETH APR ===");
    match apr {
        Some(v) => {
            println!("Current 7-day average stETH APR: {:.2}%", v);
            println!(
                "Note: This is post-10%-fee rate. Rewards are paid daily and compound automatically."
            );
        }
        None => {
            println!("Raw response: {}", serde_json::to_string_pretty(&body)?);
        }
    }

    Ok(())
}

fn extract_apr(body: &serde_json::Value) -> Option<f64> {
    // Try data.smaApr first
    if let Some(v) = body["data"]["smaApr"].as_f64() {
        return Some(v);
    }
    // Try data.aprs[0].apr
    if let Some(arr) = body["data"]["aprs"].as_array() {
        if let Some(first) = arr.first() {
            if let Some(v) = first["apr"].as_f64() {
                return Some(v);
            }
        }
    }
    // Try data.apr directly
    if let Some(v) = body["data"]["apr"].as_f64() {
        return Some(v);
    }
    None
}
