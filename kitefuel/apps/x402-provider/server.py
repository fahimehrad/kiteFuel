"""
KiteFuel Market Data — x402 Provider Service
=============================================
Implements the Kite Service Provider x402 flow:

  Step 1  Client calls GET /api/market-brief?symbol=BTC  (no X-PAYMENT)
  Step 2  Service returns HTTP 402 with payment requirements
  Step 3  Client obtains a real X-PAYMENT token via Kite Passport / MCP
  Step 4  Client retries:  GET /api/market-brief?symbol=BTC  + X-PAYMENT header
  Step 5  Service calls POST https://facilitator.pieverse.io/v2/settle
  Step 6  If settled → return paid market data (200)
          If rejected → return HTTP 402 again

Payment token details:
  - The x402 asset is the Kite testnet stablecoin (Test USDT) at
    0x0fF5393387ad2f9f691FD6Fd28e07E3969e27e63
  - The facilitator executes transferWithAuthorization for that token on Kite Chain testnet.
  - The provider wallet receives the x402 payment token directly; this service never
    handles keys or signs on-chain transactions.
  - "KITE" in response fields refers to the KiteFuel platform denomination, not the
    native gas token. The x402 payment itself settles in the testnet payment token.

Run standalone:
  uvicorn server:app --host 0.0.0.0 --port 9000

Environment variables:
  PROVIDER_WALLET_ADDRESS  – wallet that receives x402 payment token settlements
  SERVICE_URL              – public base URL of this service (e.g. https://your-service.com)
  FACILITATOR_BASE_URL     – (optional) default https://facilitator.pieverse.io
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROVIDER_WALLET  = os.environ.get("PROVIDER_WALLET_ADDRESS", "0x0000000000000000000000000000000000000000")
SERVICE_URL      = os.environ.get("SERVICE_URL", "http://localhost:9000").rstrip("/")
FACILITATOR_BASE = os.environ.get("FACILITATOR_BASE_URL", "https://facilitator.pieverse.io")
SETTLE_ENDPOINT  = f"{FACILITATOR_BASE}/v2/settle"

# x402 payment token: Kite testnet stablecoin (Test USDT) — not the native KITE gas token
KITE_ASSET    = "0x0fF5393387ad2f9f691FD6Fd28e07E3969e27e63"
KITE_NETWORK  = "kite-testnet"
KITE_SCHEME   = "gokite-aa"
# 5 units of the payment token (18 decimals)
MAX_AMOUNT    = "5000000000000000000"

FACILITATOR_TIMEOUT = 30  # seconds

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="KiteFuel Market Data",
    version="1.0.0",
    description="Pay-per-brief market intelligence for AI agents, powered by x402.",
)

# ---------------------------------------------------------------------------
# Payment requirements builder
# ---------------------------------------------------------------------------

def _payment_requirements() -> dict[str, Any]:
    return {
        "error": "X-PAYMENT header is required",
        "accepts": [
            {
                "scheme": KITE_SCHEME,
                "network": KITE_NETWORK,
                "maxAmountRequired": MAX_AMOUNT,
                "resource": f"{SERVICE_URL}/api/market-brief",
                "description": "KiteFuel Market Data — pay-per-brief intelligence for AI agents",
                "mimeType": "application/json",
                "outputSchema": {
                    "input": {
                        "discoverable": True,
                        "method": "GET",
                        "queryParams": {
                            "symbol": {
                                "description": "Asset symbol e.g. BTC, ETH",
                                "required": True,
                                "type": "string",
                            }
                        },
                        "type": "http",
                    },
                    "output": {
                        "properties": {
                            "symbol":    {"type": "string"},
                            "price_usd": {"type": "number"},
                            "trend":     {"type": "string"},
                            "summary":   {"type": "string"},
                        },
                        "required": ["symbol", "price_usd", "trend", "summary"],
                        "type": "object",
                    },
                },
                "payTo":             PROVIDER_WALLET,
                "maxTimeoutSeconds": 300,
                "asset":             KITE_ASSET,
                "extra":             None,
                "merchantName":      "KiteFuel Market Data",
            }
        ],
        "x402Version": 1,
    }

# ---------------------------------------------------------------------------
# Deterministic market data (same symbol → same data)
# ---------------------------------------------------------------------------

_TRENDS  = ["bullish", "bearish", "neutral", "consolidating", "volatile"]
_SUMMARIES = [
    "{sym} is showing strong momentum backed by institutional accumulation and on-chain activity. "
    "Analysts expect continued upside as market sentiment remains positive.",

    "{sym} faces selling pressure as macro concerns weigh on risk assets globally. "
    "Short-term weakness may persist, but long-term fundamentals remain intact.",

    "{sym} is trading sideways in a tight range as the market awaits a catalyst. "
    "Volume is below average, suggesting indecision among participants.",

    "{sym} has been consolidating after a sharp rally, with bulls defending key support levels. "
    "A breakout above resistance could trigger the next leg higher.",

    "{sym} is experiencing elevated volatility driven by geopolitical headlines and large liquidations. "
    "Traders are advised to manage risk carefully in current conditions.",
]


def _market_data(symbol: str) -> dict[str, Any]:
    """Return deterministic fake market data seeded by symbol."""
    sym = symbol.upper()
    seed = int(hashlib.md5(sym.encode()).hexdigest(), 16)
    rng  = random.Random(seed)

    base_price   = rng.uniform(0.001, 70_000)
    volume_24h   = rng.uniform(1_000_000, 80_000_000_000)
    trend        = _TRENDS[seed % len(_TRENDS)]
    summary_tmpl = _SUMMARIES[seed % len(_SUMMARIES)]

    return {
        "symbol":             sym,
        "price_usd":          round(base_price, 2),
        "volume_24h":         round(volume_24h, 0),
        "trend":              trend,
        "summary":            summary_tmpl.format(sym=sym),
        "data_provider":      "KiteFuel Market Data (x402)",
        "payment_settled":    True,
        "settlement_network": KITE_NETWORK,
    }

# ---------------------------------------------------------------------------
# X-PAYMENT token decoder
# ---------------------------------------------------------------------------

def _decode_payment_token(token: str) -> dict[str, Any]:
    """Base64-decode and JSON-parse the X-PAYMENT token.

    Raises ValueError with a human-readable message on failure.
    """
    try:
        # Add padding if needed
        padded = token + "=" * (-len(token) % 4)
        raw = base64.b64decode(padded).decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Malformed X-PAYMENT token: {exc}") from exc

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "KiteFuel Market Data", "x402": True}


@app.get("/api/market-brief")
async def market_brief(
    symbol: str = Query(..., description="Asset symbol e.g. BTC, ETH"),
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
) -> JSONResponse:
    """
    Paid market-data endpoint.

    - Without X-PAYMENT → 402 with payment requirements.
    - With X-PAYMENT    → settle via facilitator → return data on success.
    """

    # ── Step 1/2: No token → 402 ────────────────────────────────────────────
    if not x_payment:
        logger.info("market_brief_unpaid", symbol=symbol)
        return JSONResponse(status_code=402, content=_payment_requirements())

    # ── Step 4: Decode the token ─────────────────────────────────────────────
    try:
        token_data = _decode_payment_token(x_payment)
    except ValueError as exc:
        logger.warning("market_brief_bad_token", symbol=symbol, error=str(exc))
        return JSONResponse(
            status_code=402,
            content={
                "error": str(exc),
                "accepts": _payment_requirements()["accepts"],
                "x402Version": 1,
            },
        )

    # ── Step 5: Call facilitator /v2/settle ──────────────────────────────────
    # The facilitator executes transferWithAuthorization for the x402 payment token
    settle_body: dict[str, Any] = {
        "authorization": token_data.get("authorization"),
        "signature":     token_data.get("signature"),
        "network":       KITE_NETWORK,
    }

    try:
        async with httpx.AsyncClient(timeout=FACILITATOR_TIMEOUT) as client:
            resp = await client.post(SETTLE_ENDPOINT, json=settle_body)
    except httpx.TimeoutException:
        logger.error("market_brief_facilitator_timeout", symbol=symbol)
        return JSONResponse(
            status_code=500,
            content={"error": "Facilitator timeout — please retry"},
        )
    except httpx.RequestError as exc:
        logger.error("market_brief_facilitator_error", symbol=symbol, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": f"Facilitator unreachable: {exc}"},
        )

    facilitator_ok = resp.is_success
    try:
        facilitator_body = resp.json()
    except Exception:
        facilitator_body = {"raw": resp.text}

    logger.info(
        "market_brief_settle_attempt",
        symbol=symbol,
        facilitator_status=resp.status_code,
        facilitator_response_summary=str(facilitator_body)[:200],
    )

    # ── Step 6: Return data or 402 ───────────────────────────────────────────
    if facilitator_ok:
        return JSONResponse(status_code=200, content=_market_data(symbol))

    # Settlement rejected — return 402 with the facilitator's error
    error_msg = (
        facilitator_body.get("error")
        or facilitator_body.get("message")
        or f"Facilitator rejected settlement (HTTP {resp.status_code})"
    )
    return JSONResponse(
        status_code=402,
        content={
            "error": error_msg,
            "accepts": _payment_requirements()["accepts"],
            "x402Version": 1,
        },
    )
