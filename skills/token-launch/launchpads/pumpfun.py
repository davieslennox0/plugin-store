"""
一键发币 v1.0 — pump.fun adapter (via PumpPortal API).

Flow:
  1. Generate ephemeral creator keypair + mint keypair
  2. Fund creator keypair from onchainos wallet (~0.02 SOL)
  3. Get unsigned TX from PumpPortal /api/trade-local (array format)
  4. Deserialize → sign with BOTH keypairs locally
  5. Broadcast directly to Solana RPC
  6. Wait for confirmation

Uses ephemeral creator keypair as fee payer so we can fully sign
locally without needing TEE partial-signature support.

PumpPortal docs: https://pumpportal.fun/creation/
"""
from __future__ import annotations

import asyncio
import base64
import json
import struct
import time

import base58
import httpx

import config as C
from .base import LaunchpadAdapter, LaunchParams, LaunchResult, onchainos_bin

_SOLANA_EXPLORER = "https://solscan.io/tx"
_PUMPFUN_TRADE = "https://pump.fun"
_SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# SOL needed to fund the ephemeral creator for token creation
# Covers rent (~0.015 SOL) + priority fee + compute + some buffer
_CREATOR_FUND_SOL = 0.025


class PumpFunAdapter(LaunchpadAdapter):

    @property
    def name(self) -> str:
        return "pumpfun"

    @property
    def display_name(self) -> str:
        return "pump.fun"

    @property
    def chain(self) -> str:
        return "solana"

    def _fee_estimate(self, params: LaunchParams) -> float:
        pf = params.extras.get("priority_fee", C.PUMPFUN_PRIORITY_FEE)
        return pf + _CREATOR_FUND_SOL

    async def launch(self, params: LaunchParams) -> LaunchResult:
        """Launch a token on pump.fun via PumpPortal."""

        if C.DRY_RUN:
            return LaunchResult(
                success=True,
                token_address="DRY_RUN_NO_TOKEN_ADDRESS",
                tx_hash="DRY_RUN_NO_TX_HASH",
                error="DRY_RUN mode — no on-chain TX sent",
            )

        from solders.keypair import Keypair as SoldersKeypair
        from solders.transaction import VersionedTransaction

        # ── 1. Generate keypairs ────────────────────────────────────────
        creator_kp = SoldersKeypair()   # ephemeral fee payer
        mint_kp = SoldersKeypair()      # token mint
        creator_pub = str(creator_kp.pubkey())
        mint_pubkey = str(mint_kp.pubkey())

        print(f"  [pump.fun] Creator (ephemeral): {creator_pub[:8]}...{creator_pub[-4:]}")
        print(f"  [pump.fun] Mint address: {mint_pubkey}")

        # ── 2. Fund creator keypair ─────────────────────────────────────
        fund_amount = _CREATOR_FUND_SOL + params.buy_amount
        print(f"  [pump.fun] Funding creator with {fund_amount} SOL...")

        fund_hash = await self._fund_creator(creator_pub, fund_amount)
        if not fund_hash:
            return LaunchResult(
                success=False,
                error="Failed to fund ephemeral creator keypair",
            )

        print(f"  [pump.fun] Funding TX: {fund_hash[:12]}...")

        # Wait for funding to confirm (check creator balance directly)
        funded = await self._wait_funding(creator_pub)
        if not funded:
            return LaunchResult(
                success=False,
                error="Funding TX did not confirm in time",
            )

        # ── 3–6: Post-funding steps (wrapped for sweep-back on failure) ─
        try:
            result = await self._execute_after_funding(
                params, creator_kp, mint_kp, creator_pub, mint_pubkey,
            )
        except Exception as e:
            result = LaunchResult(success=False, error=f"Unexpected error: {e}")

        # If launch failed, attempt to sweep remaining SOL back to wallet
        if not result.success and params.wallet_address:
            await self._sweep_back(creator_kp, params.wallet_address)

        return result

    async def _execute_after_funding(
        self, params: LaunchParams, creator_kp, mint_kp,
        creator_pub: str, mint_pubkey: str,
    ) -> LaunchResult:
        """Steps 3-6: PumpPortal API → sign → broadcast → confirm."""
        from solders.transaction import VersionedTransaction

        # ── 3. Get unsigned TX from PumpPortal ──────────────────────────
        pool = params.extras.get("pool", C.PUMPFUN_POOL)
        priority_fee = params.extras.get("priority_fee", C.PUMPFUN_PRIORITY_FEE)

        create_payload = [
            {
                "publicKey": creator_pub,   # ephemeral creator is the fee payer
                "action": "create",
                "tokenMetadata": {
                    "name": params.name,
                    "symbol": params.symbol,
                    "uri": params.metadata_uri,
                },
                "mint": mint_pubkey,
                "denominatedInSol": "true",
                "amount": params.buy_amount,
                "slippage": params.slippage_bps / 100,
                "priorityFee": priority_fee,
                "pool": pool,
            }
        ]

        async with httpx.AsyncClient(timeout=C.PUMPFUN_TX_TIMEOUT) as client:
            resp = await client.post(
                f"{C.PUMPFUN_API_BASE}/api/trade-local",
                headers={"Content-Type": "application/json"},
                json=create_payload,
            )

        if resp.status_code != 200:
            return LaunchResult(
                success=False,
                error=f"PumpPortal API error {resp.status_code}: {resp.text}",
            )

        tx_list = resp.json()
        if not tx_list or not isinstance(tx_list, list):
            return LaunchResult(
                success=False,
                error=f"PumpPortal returned unexpected response: {resp.text[:200]}",
            )

        tx_encoded = tx_list[0]

        # ── 4. Deserialize and sign with BOTH keypairs ──────────────────
        print("  [pump.fun] Signing with both keypairs...")
        try:
            tx_bytes = base58.b58decode(tx_encoded)
            tx = VersionedTransaction.from_bytes(tx_bytes)

            # Re-create TX signed with both creator + mint keypairs
            signed_tx = VersionedTransaction(tx.message, [creator_kp, mint_kp])
            signed_bytes = bytes(signed_tx)

            print("  [pump.fun] TX fully signed locally")
        except Exception as e:
            return LaunchResult(
                success=False,
                error=f"TX signing failed: {e}",
            )

        # ── 5. Broadcast directly to Solana RPC ────────────────────────
        print("  [pump.fun] Broadcasting to Solana...")
        tx_hash = await self._broadcast_solana(signed_bytes)

        if not tx_hash:
            return LaunchResult(
                success=False,
                error="Failed to broadcast TX to Solana",
            )

        # ── 6. Wait for confirmation ────────────────────────────────────
        print(f"  [pump.fun] TX submitted: {tx_hash}")
        print("  [pump.fun] Waiting for confirmation...")

        confirmed = await self._wait_solana_confirmation(tx_hash)

        return LaunchResult(
            success=confirmed,
            token_address=mint_pubkey,
            tx_hash=tx_hash,
            explorer_url=f"{_SOLANA_EXPLORER}/{tx_hash}",
            trade_page_url=f"{_PUMPFUN_TRADE}/{mint_pubkey}",
            error="" if confirmed else "Transaction not confirmed within timeout",
        )

    async def _sweep_back(self, creator_kp, destination: str):
        """Best-effort sweep remaining SOL from ephemeral keypair back to wallet.

        Constructs a raw SOL transfer (system program) signed by the ephemeral
        keypair and broadcasts it directly — no onchainos CLI needed.
        """
        from solders.keypair import Keypair as SoldersKeypair
        from solders.pubkey import Pubkey
        from solders.system_program import transfer, TransferParams
        from solders.transaction import Transaction
        from solders.message import Message
        from solders.hash import Hash

        creator_pub = str(creator_kp.pubkey())
        print(f"  [pump.fun] Sweeping remaining SOL back from {creator_pub[:8]}...")

        try:
            # Get current balance
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(_SOLANA_RPC, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getBalance",
                    "params": [creator_pub, {"commitment": "confirmed"}],
                })
            lamports = resp.json().get("result", {}).get("value", 0)
            if lamports <= 5000:  # Not enough to cover TX fee
                print(f"  [pump.fun] Nothing to sweep ({lamports} lamports)")
                return

            # Get recent blockhash
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(_SOLANA_RPC, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getLatestBlockhash",
                    "params": [{"commitment": "confirmed"}],
                })
            blockhash_str = resp.json()["result"]["value"]["blockhash"]
            blockhash = Hash.from_string(blockhash_str)

            # Transfer all minus fee (5000 lamports)
            sweep_amount = lamports - 5000
            dest_pubkey = Pubkey.from_string(destination)

            ix = transfer(TransferParams(
                from_pubkey=creator_kp.pubkey(),
                to_pubkey=dest_pubkey,
                lamports=sweep_amount,
            ))

            msg = Message.new_with_blockhash([ix], creator_kp.pubkey(), blockhash)
            tx = Transaction.new_unsigned(msg)
            tx.sign([creator_kp], blockhash)

            # Broadcast
            tx_bytes = bytes(tx)
            tx_b64 = base64.b64encode(tx_bytes).decode()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(_SOLANA_RPC, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "sendTransaction",
                    "params": [tx_b64, {"encoding": "base64", "skipPreflight": False}],
                })
            result = resp.json()
            if "error" in result:
                print(f"  [pump.fun] Sweep failed: {result['error'].get('message', '')}")
            else:
                swept_sol = sweep_amount / 1_000_000_000
                print(f"  [pump.fun] Swept {swept_sol:.4f} SOL back to wallet")

        except Exception as e:
            print(f"  [pump.fun] Sweep error (funds may remain in {creator_pub}): {e}")

    async def _fund_creator(self, creator_address: str, amount: float) -> str:
        """Send SOL from onchainos wallet to the ephemeral creator address.

        Returns TX hash or empty string on failure.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                onchainos_bin(), "wallet", "send",
                "--chain", "501",
                "--receipt", creator_address,
                "--readable-amount", str(amount),
                "--force",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode().strip() if stderr else "unknown error"
                print(f"  [pump.fun] Funding failed: {err}")
                return ""

            output = json.loads(stdout.decode())
            data = output.get("data", {})
            if isinstance(data, list) and data:
                data = data[0]
            return data.get("txHash", "") if isinstance(data, dict) else ""

        except Exception as e:
            print(f"  [pump.fun] Funding error: {e}")
            return ""

    async def _wait_funding(self, creator_address: str, max_retries: int = 20) -> bool:
        """Wait for creator address to have SOL balance on-chain."""
        delays = [0.5, 0.5, 1, 1] + [2] * (max_retries - 4)
        async with httpx.AsyncClient(timeout=10) as client:
            for i in range(max_retries):
                await asyncio.sleep(delays[i] if i < len(delays) else 2)
                try:
                    resp = await client.post(_SOLANA_RPC, json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getBalance",
                        "params": [creator_address, {"commitment": "confirmed"}],
                    })
                    result = resp.json()
                    lamports = result.get("result", {}).get("value", 0)
                    if lamports > 0:
                        sol = lamports / 1_000_000_000
                        print(f"  [pump.fun] Creator funded: {sol:.4f} SOL ({i + 1} polls)")
                        return True
                except Exception:
                    pass
                if (i + 1) % 3 == 0:
                    print(f"  [pump.fun] Waiting for funding... ({i + 1}/{max_retries})")
        return False

    async def _broadcast_solana(self, signed_tx_bytes: bytes) -> str:
        """Send fully signed TX directly to Solana RPC.

        Returns the TX signature (hash) or empty string on failure.
        """
        tx_b64 = base64.b64encode(signed_tx_bytes).decode()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(_SOLANA_RPC, json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sendTransaction",
                    "params": [tx_b64, {
                        "encoding": "base64",
                        "skipPreflight": False,
                        "preflightCommitment": "confirmed",
                        "maxRetries": 3,
                    }],
                })
            result = resp.json()

            if "error" in result:
                err = result["error"]
                print(f"  [pump.fun] RPC error: {err.get('message', err)}")
                # Include logs if available
                data = err.get("data", {})
                if isinstance(data, dict):
                    for log in data.get("logs", [])[-5:]:
                        print(f"    {log}")
                return ""

            return result.get("result", "")

        except Exception as e:
            print(f"  [pump.fun] Broadcast error: {e}")
            return ""

    async def _wait_solana_confirmation(self, tx_hash: str, max_retries: int = 15) -> bool:
        """Poll Solana RPC for TX confirmation."""
        delays = [0.5, 0.5, 1, 1] + [2] * (max_retries - 4)
        async with httpx.AsyncClient(timeout=10) as client:
            for i in range(max_retries):
                await asyncio.sleep(delays[i] if i < len(delays) else 2)
                try:
                    resp = await client.post(_SOLANA_RPC, json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignatureStatuses",
                        "params": [[tx_hash], {"searchTransactionHistory": True}],
                    })
                    result = resp.json()
                    statuses = result.get("result", {}).get("value", [])
                    if statuses and statuses[0]:
                        status = statuses[0]
                        if status.get("err"):
                            print(f"  [pump.fun] TX failed: {status['err']}")
                            return False
                        conf = status.get("confirmationStatus", "")
                        if conf in ("confirmed", "finalized"):
                            print(f"  [pump.fun] {conf.capitalize()}! ({i + 1} polls)")
                            return True
                except Exception:
                    pass
                if (i + 1) % 3 == 0:
                    print(f"  [pump.fun] Waiting for confirmation... ({i + 1}/{max_retries})")
        return False
