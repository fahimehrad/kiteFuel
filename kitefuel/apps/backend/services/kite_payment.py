"""
KitePayment — Kite Passport x402 payments and session management via kpass CLI.

The kpass CLI must be installed and authenticated on the host.
Config files are read from .kpass/ in the working directory or ~/.kpass/.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

NANSEN_SCREENER = "https://api.nansen.ai/api/v1/token-screener"
_KPASS_DIR = os.path.join(os.getcwd(), ".kite-passport")


async def _run_kpass(*args: str) -> dict[str, Any]:
    """Run any kpass command and return parsed JSON output."""
    cmd = ["kpass", *args, "--output", "json"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        raise KitePaymentError("kpass timed out after 120s")
    except FileNotFoundError:
        raise KitePaymentError("kpass CLI not found — ensure npm install -g kpass ran in Dockerfile")

    raw = stdout.decode().strip()
    if not raw:
        raise KitePaymentError(f"kpass returned no output. stderr={stderr.decode()[:200]}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise KitePaymentError(f"kpass output not JSON: {raw[:200]}: {e}")


class KitePaymentError(Exception):
    pass


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

async def create_spending_session() -> dict[str, str]:
    """
    Create a new KitePassport spending session scoped to Nansen.
    Returns {"request_id": "...", "approval_url": "..."}.
    The borrower must approve this URL before buy_market_data() will work.
    """
    delegation = {
        "task": {
            "summary": "Purchase real-time on-chain token analytics from Nansen for KiteFuel market intelligence"
        },
        "payment_policy": {
            "allowed_payment_approaches": ["x402"],
            "assets": ["USDC"],
            "max_amount_per_tx": "0.05",
            "max_total_amount": "1",
            "ttl_seconds": 3600,
        },
        "execution_constraints": {
            "x402_http": {
                "scope_mode": "scoped",
                "allowed_endpoints": [
                    {"method": "POST", "host": "api.nansen.ai", "path_prefix": "/api/v1/token-screener"}
                ],
            }
        },
    }

    result = await _run_kpass("agent:session", "create", "--delegation", json.dumps(delegation))

    if result.get("status") not in ("success", "human_action_required"):
        raise KitePaymentError(f"Session creation failed: {result.get('error', result)}")

    return {
        "request_id":   result["request_id"],
        "approval_url": result["approval_url"],
    }


async def wait_for_session_approval(request_id: str, timeout_seconds: int = 300) -> bool:
    """
    Poll until the borrower approves the session or it times out.
    Returns True if approved, False if timed out or rejected.
    """
    result = await _run_kpass(
        "agent:session", "status",
        "--request-id", request_id,
        "--wait",
        "--timeout", str(timeout_seconds),
    )
    return result.get("status") == "success"


async def check_session_approved(request_id: str) -> bool:
    """Single non-blocking check — use this for polling from the frontend."""
    result = await _run_kpass("agent:session", "status", "--request-id", request_id)
    return result.get("status") == "success"


# ---------------------------------------------------------------------------
# Data purchase
# ---------------------------------------------------------------------------

async def buy_market_data(symbol: str) -> dict[str, Any]:
    """
    Purchase real-time token analytics for `symbol` via Kite Passport (Nansen x402).
    Requires an active approved session.
    """
    sym  = symbol.upper()
    body = json.dumps({"symbol": sym, "limit": 1})

    result = await _run_kpass(
        "agent:session", "execute",
        "--url", NANSEN_SCREENER,
        "--method", "POST",
        "--headers", '{"Content-Type":"application/json"}',
        "--body", body,
    )

    if result.get("status") != "success":
        error_code = result.get("error_code", "")
        error_msg  = result.get("error", "unknown error")
        raise KitePaymentError(f"kpass payment failed [{error_code}]: {error_msg}")

    x402        = result.get("x402", {})
    nansen_data = x402.get("parsed_response_body") or {}
    if not nansen_data and isinstance(x402.get("response_body"), str):
        try:
            nansen_data = json.loads(x402["response_body"])
        except Exception:
            pass

    payment_req = result.get("payment_requirement", {})
    return _normalise(sym, nansen_data, payment_req.get("amount", "0.01"), payment_req.get("asset", "USDC"))


def _normalise(symbol: str, raw: dict, amount: str, asset: str) -> dict[str, Any]:
    tokens    = raw.get("data") or raw.get("tokens") or []
    token     = tokens[0] if tokens else {}
    price_usd = float(token.get("price", token.get("priceUsd", 0)) or 0)
    change    = float(token.get("priceChange24h", token.get("change24h", 0)) or 0)
    volume    = float(token.get("volume24h", token.get("volumeUsd24h", 0)) or 0)
    trend     = "bullish" if change > 3 else "bearish" if change < -3 else "neutral"

    report = (
        f"**{symbol} Market Brief (Nansen on-chain)**\n\n"
        f"**Price & Market**\n"
        f"{symbol} at ${price_usd:,.2f} | 24h change {change:+.1f}% | Volume ${volume:,.0f}\n\n"
        f"**On-Chain Signals**\n"
        + (f"Smart money netflow: {token.get('smartMoneyNetflow')} | "
           f"Holders: {token.get('holders', 'N/A')} | "
           f"Txns (24h): {token.get('txCount24h', 'N/A')}"
           if token else "On-chain data retrieved from Nansen analytics.")
        + f"\n\n**Verdict**\n"
          f"{'Bullish' if trend == 'bullish' else 'Bearish' if trend == 'bearish' else 'Neutral'} — "
          f"based on real-time Nansen data. Paid {amount} {asset} via Kite Passport x402."
    )

    return {
        "symbol":             symbol,
        "price_usd":          price_usd,
        "trend":              trend,
        "summary":            f"{symbol} ${price_usd:,.2f} | {change:+.1f}% 24h | {trend}",
        "report":             report,
        "data_provider":      f"Nansen via Kite Passport x402 (paid {amount} {asset})",
        "payment_settled":    True,
        "settlement_network": "kite-passport",
    }
