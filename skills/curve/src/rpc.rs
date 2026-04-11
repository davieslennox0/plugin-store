// rpc.rs — Direct eth_call utilities (no onchainos)

/// Multicall3 contract — deployed at the same address on all major EVM chains.
const MULTICALL3: &str = "0xcA11bde05977b3631167028862bE2a173976CA11";

/// Perform a raw JSON-RPC eth_call
pub async fn eth_call(to: &str, data: &str, rpc_url: &str) -> anyhow::Result<String> {
    let client = reqwest::Client::new();
    let body = serde_json::json!({
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {"to": to, "data": data},
            "latest"
        ],
        "id": 1
    });
    let resp: serde_json::Value = client.post(rpc_url).json(&body).send().await?.json().await?;
    if let Some(err) = resp.get("error") {
        anyhow::bail!("eth_call error: {}", err);
    }
    Ok(resp["result"].as_str().unwrap_or("0x").to_string())
}

/// balanceOf(address) for an ERC-20 (selector 0x70a08231)
pub async fn balance_of(token: &str, owner: &str, rpc_url: &str) -> anyhow::Result<u128> {
    let owner_clean = owner.trim_start_matches("0x");
    let owner_padded = format!("{:0>64}", owner_clean);
    let data = format!("0x70a08231{}", owner_padded);
    let hex = eth_call(token, &data, rpc_url).await?;
    Ok(u128::from_str_radix(hex.trim_start_matches("0x"), 16).unwrap_or(0))
}

/// allowance(address owner, address spender) selector = 0xdd62ed3e
pub async fn get_allowance(
    token: &str,
    owner: &str,
    spender: &str,
    rpc_url: &str,
) -> anyhow::Result<u128> {
    let owner_clean = owner.trim_start_matches("0x");
    let spender_clean = spender.trim_start_matches("0x");
    let owner_padded = format!("{:0>64}", owner_clean);
    let spender_padded = format!("{:0>64}", spender_clean);
    let data = format!("0xdd62ed3e{}{}", owner_padded, spender_padded);
    let hex = eth_call(token, &data, rpc_url).await?;
    Ok(u128::from_str_radix(hex.trim_start_matches("0x"), 16).unwrap_or(0))
}

/// Batch balanceOf(owner) calls via Multicall3 aggregate3.
///
/// Replaces N sequential eth_calls with a single call to the Multicall3 contract.
/// token_addrs and the returned Vec have the same length and order.
/// Individual failures return 0 (allowFailure = true).
///
/// Encoding: aggregate3((address target, bool allowFailure, bytes callData)[])
/// Selector: 0x82ad56cb
pub async fn multicall_balance_of(
    token_addrs: &[&str],
    owner: &str,
    rpc_url: &str,
) -> anyhow::Result<Vec<u128>> {
    let n = token_addrs.len();
    if n == 0 {
        return Ok(vec![]);
    }

    // balanceOf(address) calldata: selector (4 bytes) + owner padded to 32 bytes = 36 bytes
    let owner_padded = format!("{:0>64}", owner.trim_start_matches("0x"));
    let balance_of_hex = format!("70a08231{}", owner_padded); // 72 hex chars = 36 bytes

    // ABI-encode aggregate3 input
    // Layout (all in hex, no 0x):
    //   selector (8 hex) | offset_to_array=0x20 (64) | array_len=N (64)
    //   | N×offset_pointers (each 64) | N×struct_encodings (each 384 = 192 bytes)
    //
    // Each struct (address, bool, bytes=36 bytes):
    //   [0]   address right-padded to 32 bytes
    //   [32]  allowFailure = 1
    //   [64]  offset to bytes within struct = 96 (0x60)
    //   [96]  bytes length = 36 (0x24)
    //   [128] first 32 bytes of calldata  (selector + first 28 bytes of padded owner)
    //   [160] last 4 bytes of calldata + 28 zero-bytes padding
    //
    // struct[i] offset (relative to start of array body after length word) = N*32 + i*192

    let mut hex_data = String::with_capacity(8 + 128 + n * 64 + n * 384);
    hex_data.push_str("82ad56cb");
    hex_data.push_str(&format!("{:0>64x}", 32u64));   // outer offset = 0x20
    hex_data.push_str(&format!("{:0>64x}", n as u64)); // array length

    for i in 0..n {
        let offset = n * 32 + i * 192;
        hex_data.push_str(&format!("{:0>64x}", offset as u64));
    }
    for addr in token_addrs {
        let addr_clean = addr.trim_start_matches("0x");
        hex_data.push_str(&format!("{:0>64}", addr_clean)); // address
        hex_data.push_str(&format!("{:0>64x}", 1u64));      // allowFailure = true
        hex_data.push_str(&format!("{:0>64x}", 96u64));     // bytes offset within struct
        hex_data.push_str(&format!("{:0>64x}", 36u64));     // bytes length = 36
        hex_data.push_str(&balance_of_hex[..64]);            // first 32 bytes of calldata
        hex_data.push_str(&balance_of_hex[64..]);            // last 4 bytes of calldata
        hex_data.push_str(&"0".repeat(56));                  // 28 bytes padding
    }

    let calldata = format!("0x{}", hex_data);
    let result_hex = eth_call(MULTICALL3, &calldata, rpc_url).await?;
    let clean = &result_hex[2..]; // strip "0x" prefix only (not leading zeros)

    // Convert hex string → bytes
    let bytes: Vec<u8> = (0..clean.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&clean[i..i + 2], 16).unwrap_or(0))
        .collect();

    // Decode (bool success, bytes returnData)[]
    // [0:32]   outer offset = 0x20
    // [32:64]  array length N
    // [64:64+N*32]  N offset pointers (each 32 bytes, relative to array content start at byte 64)
    //
    // Each element (bool, bytes):
    //   [+0:+32]   bool success
    //   [+32:+64]  offset to bytes data within element (= 0x40 = 64 when bytes.length > 0)
    //   [+64:+96]  bytes length (= 32 for successful balanceOf; = 0 for failed/reverted call)
    //   [+96:+128] bytes data (present only when length > 0)
    //
    // IMPORTANT: elements have variable size — failed calls (bytes.length=0) produce 96-byte
    // elements, successful calls 128 bytes. We must read actual offset pointers rather than
    // computing elem position as 64 + N*32 + i*128 (which would misalign after any failed call).

    let mut balances = vec![0u128; n];
    for i in 0..n {
        // Read the actual offset for element[i] from the offset pointer table
        let ptr_start = 64 + i * 32;
        if ptr_start + 32 > bytes.len() {
            break;
        }
        // Offset is a uint256 (big-endian); we only need the low usize bytes
        let mut off_buf = [0u8; 8];
        off_buf.copy_from_slice(&bytes[ptr_start + 24..ptr_start + 32]);
        let elem_offset = usize::from_be_bytes(off_buf);
        // Element absolute position = array content start (64) + element offset
        let elem = 64 + elem_offset;

        // Check success flag (last byte of 32-byte bool word)
        if bytes.get(elem + 31).copied().unwrap_or(0) == 0 {
            continue; // call reverted — skip
        }

        // bytes length is at element offset + 64 (after bool + bytes-ptr-word)
        let len_pos = elem + 64;
        if len_pos + 32 > bytes.len() {
            continue;
        }
        let mut len_buf = [0u8; 8];
        len_buf.copy_from_slice(&bytes[len_pos + 24..len_pos + 32]);
        let data_len = usize::from_be_bytes(len_buf);
        if data_len < 16 {
            continue; // need at least 16 bytes to extract u128
        }

        let data_start = elem + 96;
        let data_end = data_start + data_len;
        if data_end > bytes.len() {
            continue;
        }
        let mut buf = [0u8; 16];
        buf.copy_from_slice(&bytes[data_end - 16..data_end]);
        balances[i] = u128::from_be_bytes(buf);
    }

    Ok(balances)
}

/// Decode a 32-byte ABI-encoded uint256 result to u128
pub fn decode_uint128(hex: &str) -> u128 {
    let clean = hex.trim_start_matches("0x");
    // take last 32 hex chars (16 bytes = u128 range)
    let last32 = if clean.len() >= 32 { &clean[clean.len() - 32..] } else { clean };
    u128::from_str_radix(last32, 16).unwrap_or(0)
}
