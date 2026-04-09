#[allow(dead_code)]
pub const SOLANA_CHAIN_ID: &str = "501";
#[allow(dead_code)]
pub const SOL_NATIVE_MINT: &str = "So11111111111111111111111111111111111111112";
#[allow(dead_code)]
pub const USDC_SOLANA: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

pub const DATA_API_BASE: &str = "https://api-v3.raydium.io";
pub const TX_API_BASE: &str = "https://transaction-v1.raydium.io";

// Raydium AMM V4 program (standard pools — used as --to for onchainos contract-call)
pub const RAYDIUM_AMM_PROGRAM: &str = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8";

// Default compute unit price in micro-lamports (avoid "auto" which the API rejects)
pub const DEFAULT_COMPUTE_UNIT_PRICE: &str = "1000";

pub const DEFAULT_SLIPPAGE_BPS: u32 = 50;
pub const DEFAULT_TX_VERSION: &str = "V0";

pub const PRICE_IMPACT_WARN_PCT: f64 = 5.0;
pub const PRICE_IMPACT_BLOCK_PCT: f64 = 20.0;
