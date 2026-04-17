pub async fn run() -> anyhow::Result<()> {
    eprintln!("Checking wallet on BSC...");

    match crate::onchainos::resolve_wallet(56).await {
        Ok(wallet) if !wallet.is_empty() => {
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "ok": true,
                    "about": "PancakeSwap V3 CLMM plugin — stake LP NFTs, harvest CAKE rewards, and collect swap fees across BSC, Ethereum, Base, and Arbitrum.",
                    "wallet": wallet,
                    "chain": "BSC",
                    "chain_id": 56,
                    "status": "ready",
                    "suggestion": "Stake a V3 LP NFT to earn CAKE rewards, or view your existing positions.",
                    "next_command": "pancakeswap-clmm-plugin positions",
                    "onboarding_steps": [
                        "1. View your V3 LP positions:",
                        "   pancakeswap-clmm-plugin positions",
                        "2. Check active farming pools:",
                        "   pancakeswap-clmm-plugin farm-pools",
                        "3. Stake a position (replace 12345 with your token ID):",
                        "   pancakeswap-clmm-plugin --chain 56 farm --token-id 12345 --confirm",
                        "4. Check pending CAKE rewards:",
                        "   pancakeswap-clmm-plugin pending-rewards --token-id 12345",
                        "5. Harvest CAKE rewards:",
                        "   pancakeswap-clmm-plugin --chain 56 harvest --token-id 12345 --confirm"
                    ]
                }))?
            );
        }
        _ => {
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "ok": false,
                    "error": "No wallet found. Run: onchainos wallet login your@email.com"
                }))?
            );
        }
    }

    Ok(())
}
