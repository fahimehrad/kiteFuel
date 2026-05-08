# KiteFuel Market Data — x402 Provider

A standalone FastAPI service that sells per-request market intelligence using the
[x402](https://github.com/coinbase/x402) payment protocol on **Kite Chain testnet**.

---

## How it works

```
Client                     x402-provider               Kite Facilitator
  │                              │                            │
  │  GET /api/market-brief       │                            │
  │  (no X-PAYMENT header)       │                            │
  │ ─────────────────────────►   │                            │
  │  ◄── HTTP 402 + requirements │                            │
  │                              │                            │
  │  [obtain X-PAYMENT token via Kite Passport / MCP]         │
  │                              │                            │
  │  GET /api/market-brief       │                            │
  │  X-PAYMENT: <base64 token>   │                            │
  │ ─────────────────────────►   │                            │
  │                              │  POST /v2/settle           │
  │                              │ ─────────────────────────► │
  │                              │  ◄── 200 (settled)         │
  │  ◄── 200 market data         │                            │
```

1. **No payment** → HTTP 402 with `accepts[]` describing how to pay
2. **Client obtains token** via Kite Passport MCP (`approve_payment()`)
3. **Retry with `X-PAYMENT`** header (base64-encoded JSON with `authorization` + `signature`)
4. Provider calls **`POST https://facilitator.pieverse.io/v2/settle`** — never settles on-chain directly
5. On success → return paid market data; on failure → HTTP 402 again

---

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
export PROVIDER_WALLET_ADDRESS=0xYourWalletAddress
export SERVICE_URL=http://localhost:9000

# Start
uvicorn server:app --host 0.0.0.0 --port 9000 --reload
```

---

## Running with Docker Compose

```bash
# From kitefuel/ root:
docker compose up x402-provider
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROVIDER_WALLET_ADDRESS` | ✅ | — | Wallet that receives x402 payment token settlements |
| `SERVICE_URL` | ✅ | `http://localhost:9000` | Public base URL included in 402 requirements |
| `FACILITATOR_BASE_URL` | ❌ | `https://facilitator.pieverse.io` | Kite facilitator override |

---

## API

### `GET /health`

```json
{"status": "ok", "service": "KiteFuel Market Data", "x402": true}
```

### `GET /api/market-brief?symbol=BTC`

**Without `X-PAYMENT`** → HTTP 402:

```json
{
  "error": "X-PAYMENT header is required",
  "accepts": [{
    "scheme": "gokite-aa",
    "network": "kite-testnet",
    "maxAmountRequired": "5000000000000000000",
    "asset": "0x0fF5393387ad2f9f691FD6Fd28e07E3969e27e63",
    "payTo": "0x...",
    "merchantName": "KiteFuel Market Data",
    ...
  }],
  "x402Version": 1
}
```

**With valid `X-PAYMENT`** → HTTP 200:

```json
{
  "symbol": "BTC",
  "price_usd": 67420.50,
  "volume_24h": 28000000000,
  "trend": "bullish",
  "summary": "BTC is showing strong momentum...",
  "data_provider": "KiteFuel Market Data (x402)",
  "payment_settled": true,
  "settlement_network": "kite-testnet"
}
```

---

## curl examples

### 1. Request without payment (expect 402)

```bash
curl -s http://localhost:9000/api/market-brief?symbol=BTC | jq .
```

### 2. Request with X-PAYMENT token

```bash
TOKEN=$(echo -n '{"authorization": {...}, "signature": "0x..."}' | base64)

curl -s \
  -H "X-PAYMENT: $TOKEN" \
  "http://localhost:9000/api/market-brief?symbol=BTC" | jq .
```

---

## x402 payment details

| Field | Value |
|---|---|
| scheme | `gokite-aa` |
| network | `kite-testnet` |
| asset | `0x0fF5393387ad2f9f691FD6Fd28e07E3969e27e63` (Kite testnet stablecoin — Test USDT) |
| max amount | `5000000000000000000` (5 units of the payment token, 18 decimals) |
| facilitator | `https://facilitator.pieverse.io/v2/settle` |

### How the payment token works

The x402 asset (`0x0fF5393387ad2f9f691FD6Fd28e07E3969e27e63`) is the **Kite Chain testnet
stablecoin (Test USDT)**. It is _not_ the native KITE gas token.

When a client retries with a valid `X-PAYMENT` header, this service forwards the
`authorization` + `signature` to the Kite facilitator (`/v2/settle`).
The facilitator then executes a **`transferWithAuthorization`** call on-chain, which moves
the payment token from the payer's wallet to `PROVIDER_WALLET_ADDRESS`.
The provider service itself never signs transactions or holds keys.
