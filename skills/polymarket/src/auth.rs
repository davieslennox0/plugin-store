/// Polymarket authentication helpers.
///
/// L1: ClobAuth EIP-712 signed with local k256 key → derive API keys
/// L2: HMAC-SHA256 request signing with stored credentials
use anyhow::{Context, Result};
use base64::{engine::general_purpose, Engine as _};
use hmac::{Hmac, Mac};
use k256::ecdsa::SigningKey;
use reqwest::Client;
use serde::Deserialize;
use sha2::Sha256;

use crate::config::{save_credentials, signing_key_address, Credentials, Urls};
use crate::signing::sign_clob_auth;

// ─── L1: ClobAuth EIP-712 ────────────────────────────────────────────────────

/// Build L1 HTTP headers from a ClobAuth signature.
pub fn l1_headers(address: &str, sig: &str, timestamp: u64, nonce: u64) -> Vec<(String, String)> {
    vec![
        ("POLY_ADDRESS".to_string(), address.to_string()),
        ("POLY_SIGNATURE".to_string(), sig.to_string()),
        ("POLY_TIMESTAMP".to_string(), timestamp.to_string()),
        ("POLY_NONCE".to_string(), nonce.to_string()),
    ]
}

// ─── L2: HMAC-SHA256 ─────────────────────────────────────────────────────────

type HmacSha256 = Hmac<Sha256>;

/// Compute HMAC-SHA256 signature for a CLOB API request.
/// message = timestamp + method.to_uppercase() + request_path + body
/// Returns base64url-encoded signature.
pub fn hmac_signature(
    secret_b64url: &str,
    timestamp: u64,
    method: &str,
    path: &str,
    body: &str,
) -> Result<String> {
    // Polymarket secrets may or may not have base64 padding; normalize before decoding
    let padded = match secret_b64url.len() % 4 {
        2 => format!("{}==", secret_b64url),
        3 => format!("{}=", secret_b64url),
        _ => secret_b64url.to_string(),
    };
    let secret_bytes = general_purpose::URL_SAFE
        .decode(&padded)
        .with_context(|| format!("decoding base64url secret (len={})", secret_b64url.len()))?;

    let message = format!("{}{}{}{}", timestamp, method.to_uppercase(), path, body);

    let mut mac = HmacSha256::new_from_slice(&secret_bytes).context("creating HMAC")?;
    mac.update(message.as_bytes());
    let result = mac.finalize().into_bytes();
    // py-clob-client uses base64.urlsafe_b64encode which includes padding
    Ok(general_purpose::URL_SAFE.encode(result))
}

/// Build L2 HTTP headers for an authenticated CLOB request.
pub fn l2_headers(
    address: &str,
    api_key: &str,
    secret: &str,
    passphrase: &str,
    method: &str,
    path: &str,
    body: &str,
) -> Result<Vec<(String, String)>> {
    let timestamp = chrono::Utc::now().timestamp() as u64;
    let sig = hmac_signature(secret, timestamp, method, path, body)?;
    Ok(vec![
        ("POLY_ADDRESS".to_string(), address.to_string()),
        ("POLY_SIGNATURE".to_string(), sig),
        ("POLY_TIMESTAMP".to_string(), timestamp.to_string()),
        ("POLY_API_KEY".to_string(), api_key.to_string()),
        ("POLY_PASSPHRASE".to_string(), passphrase.to_string()),
    ])
}

// ─── API key management ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct ApiKeyResponse {
    #[serde(rename = "apiKey")]
    pub api_key: String,
    pub secret: String,
    pub passphrase: String,
}

/// Create new API keys using L1 auth with local signing key.
pub async fn create_api_key(
    client: &Client,
    signing_key: &SigningKey,
    nonce: u64,
) -> Result<Credentials> {
    let (address, sig, timestamp, nonce_used) = sign_clob_auth(signing_key, nonce)?;
    let headers = l1_headers(&address, &sig, timestamp, nonce_used);

    let mut req = client.post(format!("{}/auth/api-key", Urls::CLOB));
    for (k, v) in &headers {
        req = req.header(k.as_str(), v.as_str());
    }
    let resp: serde_json::Value = req.send().await?.json().await?;

    if let Some(err) = resp.get("error").and_then(|e| e.as_str()) {
        anyhow::bail!("Polymarket /auth/api-key failed: {}\nResponse: {}", err, resp);
    }

    let api_key_resp: ApiKeyResponse = serde_json::from_value(resp.clone())
        .with_context(|| format!("parsing api-key response: {}", resp))?;

    let creds = Credentials {
        api_key: api_key_resp.api_key,
        secret: api_key_resp.secret,
        passphrase: api_key_resp.passphrase,
        nonce,
        signing_address: address,
    };
    save_credentials(&creds)?;
    Ok(creds)
}

/// Derive existing API keys using L1 auth + same nonce.
pub async fn derive_api_key(
    client: &Client,
    signing_key: &SigningKey,
    nonce: u64,
) -> Result<Credentials> {
    let (address, sig, timestamp, _) = sign_clob_auth(signing_key, nonce)?;
    let headers = l1_headers(&address, &sig, timestamp, nonce);

    let mut req = client.get(format!("{}/auth/derive-api-key", Urls::CLOB));
    for (k, v) in &headers {
        req = req.header(k.as_str(), v.as_str());
    }
    let resp: serde_json::Value = req.send().await?.json().await?;

    if resp.get("error").is_some() {
        anyhow::bail!("derive-api-key rejected: {}", resp);
    }

    let api_key_resp: ApiKeyResponse = serde_json::from_value(resp.clone())
        .with_context(|| format!("parsing derive-api-key response: {}", resp))?;

    let creds = Credentials {
        api_key: api_key_resp.api_key,
        secret: api_key_resp.secret,
        passphrase: api_key_resp.passphrase,
        nonce,
        signing_address: address,
    };
    save_credentials(&creds)?;
    Ok(creds)
}

/// Load stored credentials or auto-derive them using the local signing key.
pub async fn ensure_credentials(
    client: &Client,
    signing_key: &SigningKey,
) -> Result<Credentials> {
    // Check environment variables first
    let env_key = std::env::var("POLYMARKET_API_KEY").unwrap_or_default();
    let env_secret = std::env::var("POLYMARKET_SECRET").unwrap_or_default();
    let env_pass = std::env::var("POLYMARKET_PASSPHRASE").unwrap_or_default();

    if !env_key.is_empty() && !env_secret.is_empty() && !env_pass.is_empty() {
        return Ok(Credentials {
            api_key: env_key,
            secret: env_secret,
            passphrase: env_pass,
            nonce: 0,
            signing_address: signing_key_address(signing_key),
        });
    }

    // Try loading from file
    if let Some(creds) = crate::config::load_credentials()? {
        return Ok(creds);
    }

    // Auto-derive via local signing key (no onchainos EIP-712 needed)
    eprintln!("[polymarket] Deriving API keys from local signing key...");
    match derive_api_key(client, signing_key, 0).await {
        Ok(c) => Ok(c),
        Err(_) => create_api_key(client, signing_key, 0).await,
    }
}
