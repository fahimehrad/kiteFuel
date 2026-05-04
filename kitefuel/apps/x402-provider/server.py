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

import anthropic
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
                            "report":    {"type": "string"},
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
# Real market brief via Exa + Nansen/CoinGecko + Anthropic Claude
# ---------------------------------------------------------------------------

async def _fetch_real_market_brief(symbol: str) -> dict[str, Any]:
    """
    Fetch a real research brief for `symbol` using:
      1. Exa  — recent news and analyst commentary
      2. Nansen — on-chain whale activity (falls back to CoinGecko if no key)
      3. Anthropic Claude — synthesizes all data into a structured brief
    """
    sym = symbol.upper()
    exa_key       = os.environ.get("EXA_API_KEY", "")
    nansen_key    = os.environ.get("NANSEN_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    exa_results  = ""
    onchain_data = ""

    # ── Exa: AI-powered web search ───────────────────────────────────────────
    if exa_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={"Authorization": f"Bearer {exa_key}", "Content-Type": "application/json"},
                    json={
                        "query": f"{sym} cryptocurrency price analysis news 2026",
                        "num_results": 4,
                        "use_autoprompt": True,
                        "type": "neural",
                        "contents": {"text": {"max_characters": 800}},
                    },
                )
            if resp.is_success:
                results = resp.json().get("results", [])
                snippets = [
                    f"- {r.get('title', '')}: {r.get('text', '')[:300]}"
                    for r in results
                ]
                exa_results = "\n".join(snippets)
                logger.info("exa_search_ok", symbol=sym, result_count=len(results))
            else:
                logger.warning("exa_search_failed", symbol=sym, status=resp.status_code)
        except Exception as exc:
            logger.warning("exa_search_error", symbol=sym, error=str(exc))

    # ── Nansen / CoinGecko: on-chain / price data ────────────────────────────
    if nansen_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://api.nansen.ai/v1/token/summary",
                    params={"symbol": sym},
                    headers={"X-Api-Key": nansen_key},
                )
            if resp.is_success:
                onchain_data = f"Nansen on-chain data: {resp.text[:600]}"
                logger.info("nansen_ok", symbol=sym)
            else:
                logger.warning("nansen_failed", symbol=sym, status=resp.status_code)
        except Exception as exc:
            logger.warning("nansen_error", symbol=sym, error=str(exc))

    # Fallback: CoinGecko free API for price data (no key needed)
    if not onchain_data:
        try:
            coin_id = sym.lower()
            id_map = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "avax": "avalanche-2"}
            coin_id = id_map.get(coin_id, coin_id)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                    params={"localization": "false", "tickers": "false", "community_data": "false"},
                )
            if resp.is_success:
                d = resp.json()
                md = d.get("market_data", {})
                price = md.get("current_price", {}).get("usd", "N/A")
                change_24h = md.get("price_change_percentage_24h", "N/A")
                vol = md.get("total_volume", {}).get("usd", "N/A")
                desc = d.get("description", {}).get("en", "")[:400]
                onchain_data = (
                    f"Price: ${price} | 24h change: {change_24h}% | Volume: ${vol}\n"
                    f"Description: {desc}"
                )
                logger.info("coingecko_ok", symbol=sym, price=price)
        except Exception as exc:
            logger.warning("coingecko_error", symbol=sym, error=str(exc))
            onchain_data = f"Price data unavailable for {sym}"

    # ── Anthropic Claude: synthesize into research brief ────────────────────
    if not anthropic_key:
        # Graceful fallback if no key — return structured placeholder
        return {
            "symbol": sym,
            "price_usd": 0,
            "trend": "unknown",
            "summary": f"[ANTHROPIC_API_KEY not set] Raw data — News: {exa_results[:200]} | On-chain: {onchain_data[:200]}",
            "report": f"News:\n{exa_results}\n\nOn-chain:\n{onchain_data}",
            "data_provider": "KiteFuel Research Service (x402)",
            "payment_settled": True,
            "settlement_network": KITE_NETWORK,
        }

    prompt = f"""You are a professional crypto research analyst. Using the data below, write a concise market brief for {sym}.

MARKET & PRICE DATA:
{onchain_data}

RECENT NEWS & ANALYSIS:
{exa_results}

Write the brief in this exact format:
**{sym} Market Brief**

**Price & Market**
[2-3 sentences on current price, volume, 24h movement]

**On-Chain Signals**
[2-3 sentences on whale activity, exchange flows, accumulation/distribution]

**News & Sentiment**
[2-3 sentences on key news headlines and market sentiment]

**Verdict**
[1 sentence: bullish / bearish / neutral with one-line reason]

Keep it under 250 words. Be specific, not generic."""

    try:
        aclient = anthropic.Anthropic(api_key=anthropic_key)
        message = aclient.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        report_text = message.content[0].text.strip()
        logger.info("anthropic_synthesis_ok", symbol=sym, tokens=message.usage.output_tokens)
    except Exception as exc:
        logger.warning("anthropic_synthesis_error", symbol=sym, error=str(exc))
        report_text = f"Research brief for {sym}:\n\nNews:\n{exa_results}\n\nOn-chain:\n{onchain_data}"

    # Extract trend from the verdict line for backwards compat
    trend = "neutral"
    report_lower = report_text.lower()
    if "bullish" in report_lower:
        trend = "bullish"
    elif "bearish" in report_lower:
        trend = "bearish"

    return {
        "symbol": sym,
        "price_usd": 0,  # embedded in report text
        "trend": trend,
        "summary": report_text[:300],  # short preview
        "report": report_text,         # full Claude-generated brief
        "data_provider": "KiteFuel Research Service (Exa + Nansen + Claude)",
        "payment_settled": True,
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
        data = await _fetch_real_market_brief(symbol)
        return JSONResponse(status_code=200, content=data)

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
