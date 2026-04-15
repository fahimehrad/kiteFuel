"""
X402Client — backend proxy for the x402 provider service.

The backend's role is strictly:
  1. Ask the x402 provider what payment is required  (request_payment_requirements)
  2. Forward a real X-PAYMENT token from the frontend to the provider  (complete_purchase)

The backend NEVER generates or signs a payment token.
Token creation is entirely the responsibility of the frontend / agent via
Kite Passport / MCP (approve_payment).
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class X402Error(Exception):
    """Raised for unexpected responses from the x402 provider (not 402 / not 200)."""


class X402PaymentRejected(Exception):
    """Raised when the x402 provider returns 402 after a payment token was forwarded.

    This means the facilitator rejected the settlement (bad token, insufficient
    funds, expired, etc.).
    """


class ConfigurationError(Exception):
    """Raised when a required environment variable (e.g. X402_PROVIDER_URL) is missing."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class X402Client:
    """
    Thin async HTTP wrapper around the x402 provider service.

    Usage:
        client = X402Client()
        requirements = await client.request_payment_requirements("BTC")
        data = await client.complete_purchase("BTC", payment_token)
    """

    #: Timeout for all HTTP requests to the x402 provider (seconds)
    TIMEOUT = 30

    def __init__(self) -> None:
        url = os.environ.get("X402_PROVIDER_URL", "").rstrip("/")
        if not url:
            raise ConfigurationError(
                "X402_PROVIDER_URL environment variable is not set. "
                "Set it to the base URL of the x402 provider service "
                "(e.g. http://localhost:9000)."
            )
        self._base_url = url

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def request_payment_requirements(self, symbol: str) -> dict[str, Any]:
        """
        Call GET /api/market-brief?symbol={symbol} without a payment token.

        Expects the x402 provider to return HTTP 402 with payment requirements.

        Returns:
            The parsed 402 JSON body (contains ``accepts`` list, ``x402Version``, etc.)

        Raises:
            X402Error: If the provider returns anything other than 402.
            ConfigurationError: If X402_PROVIDER_URL is missing (raised in __init__).
        """
        url = f"{self._base_url}/api/market-brief"
        log = logger.bind(event="x402_requirements_request", symbol=symbol, provider_url=self._base_url)
        log.info("Requesting payment requirements from x402 provider")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(url, params={"symbol": symbol})

        if resp.status_code == 402:
            body = resp.json()
            logger.info(
                "x402_402_received",
                symbol=symbol,
                provider_url=self._base_url,
                scheme=_first_accept_field(body, "scheme"),
            )
            return body

        raise X402Error(
            f"Expected HTTP 402 from x402 provider but got {resp.status_code}. "
            f"Response: {resp.text[:300]}"
        )

    async def complete_purchase(self, symbol: str, payment_token: str) -> dict[str, Any]:
        """
        Retry GET /api/market-brief?symbol={symbol} with the real X-PAYMENT token.

        The token was obtained by the frontend / agent via Kite Passport / MCP.
        The backend only forwards it — it does NOT sign or generate it.

        Returns:
            Parsed JSON market data (provider returns 200 on success).

        Raises:
            X402PaymentRejected: If the provider returns 402 again (settlement failed).
            X402Error: For any other unexpected HTTP status.
        """
        url = f"{self._base_url}/api/market-brief"
        log = logger.bind(event="x402_payment_forwarded", symbol=symbol, provider_url=self._base_url)
        log.info("Forwarding X-PAYMENT token to x402 provider")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(
                url,
                params={"symbol": symbol},
                headers={"X-PAYMENT": payment_token},
            )

        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                "x402_payment_success",
                symbol=symbol,
                provider_url=self._base_url,
                trend=data.get("trend"),
            )
            return data

        if resp.status_code == 402:
            body: dict[str, Any] = {}
            try:
                body = resp.json()
            except Exception:
                pass
            error_msg = body.get("error") or f"Provider rejected payment (HTTP 402)"
            logger.warning(
                "x402_payment_rejected",
                symbol=symbol,
                provider_url=self._base_url,
                reason=error_msg,
            )
            raise X402PaymentRejected(error_msg)

        raise X402Error(
            f"Unexpected response from x402 provider: HTTP {resp.status_code}. "
            f"Response: {resp.text[:300]}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _first_accept_field(body: dict[str, Any], field: str) -> str | None:
    """Safely extract a field from the first element of body['accepts']."""
    try:
        return body["accepts"][0][field]
    except (KeyError, IndexError, TypeError):
        return None
