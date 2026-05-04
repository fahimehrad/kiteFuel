# KiteFuel

> Programmable credit for AI agents — borrow, execute, repay on Kite Chain

---

## What it does

KiteFuel lets an autonomous AI agent borrow capital, pay for services, and settle on Kite Chain — all within a single task lifecycle enforced by a smart contract. The agent draws credit from a lender-funded escrow, purchases market data via the x402 protocol, delivers a report, and the contract repays the lender before releasing any remainder. Every step emits a verifiable on-chain event readable on KiteScan.

---

## Why it matters

AI agents that can transact autonomously need credit primitives that protect both lenders and service providers without requiring human approval at each step. Programmable escrow turns credit into a trustless, composable building block for the agentic economy.

---

## How it works

```
1. User creates task
2. Borrower agent requests credit — lender offer attached
3. Lender funds escrow on Kite Chain (KiteFuelEscrow.fundCredit)
4. Agent calls x402 market-data service (HTTP 402 payment required)
5. Kite Passport / MCP agent provides X-PAYMENT token
6. Pieverse facilitator settles the x402 payment on Kite Chain
7. Agent generates report → user registers revenue on-chain
8. Contract repays lender first (principal + fee), releases remainder
```

---

## Architecture

```
  User / Browser
       │
       ▼
  Vue 3 Frontend
       │
       ▼
  AI Agent (FastAPI Backend)  ─── x402 buy-data ──▶  x402 Provider
       │                                                    │
       │                                          Pieverse Facilitator
       │                                                    │
       └────────────────────────────────────▶  KiteFuelEscrow
                                               (Kite Chain testnet)
                                                            │
                                                        Lender
                                                  (repaid on settle)
```

---

## Kite integration points

- **x402 service provider protocol** — market-data endpoint returns `HTTP 402`; payment token forwarded by backend
- **Pieverse facilitator settlement** — validates and settles x402 X-PAYMENT tokens on Kite Chain
- **Kite Chain testnet** — all escrow, fund, revenue, and settle transactions land on Kite Chain (`chainId 2368`)
- **KiteScan attestations** — every on-chain event (`CreditFunded`, `RevenueRegistered`, `LenderRepaid`, …) is explorer-verifiable at `https://testnet.kitescan.ai/tx/{hash}`
- **Test USDT** — payment token used for x402 settlement on testnet
- **KITE native token** — used for escrow funding and gas

---

## Live demo

> 🔗 Frontend: **https://kitefuel.vercel.app** *(update after Vercel deploy)*  
> 🔗 API: **https://kitefuel-backend.railway.app** *(update after Railway deploy)*

---

## Deployed contract

> 🔗 `https://testnet.kitescan.ai/address/{CONTRACT_ADDRESS}`  
> *(replace `{CONTRACT_ADDRESS}` with the deployed address after running `python scripts/deploy_and_seed.py`)*

---

## Local setup

```bash
# 1. Clone and configure
cp .env.example .env          # fill in KITE_RPC_URL, DEPLOYER_PRIVATE_KEY, etc.

# 2. Start all services (backend, x402-provider, postgres, frontend)
docker compose up --build

# 3. Deploy contract to Kite testnet and run full happy path
python scripts/deploy_and_seed.py
# → prompts for X-PAYMENT token at the x402 confirm step

# 4. Non-interactive / CI mode
python scripts/deploy_and_seed.py --skip-deploy --payment-token "eyJ..."

# 5. View Swagger UI
open http://localhost:8000/docs
```

> **x402 token flow:** at step 3 the script pauses and prints the payment requirements.  
> Obtain an X-PAYMENT token from Kite Passport or your MCP agent, paste it, and the flow continues automatically.

---

## Tech stack

| Layer           | Technology                                                    |
|-----------------|---------------------------------------------------------------|
| Smart contracts | Solidity 0.8, Foundry                                         |
| Backend         | Python 3.12, FastAPI, SQLAlchemy, Alembic, web3.py, structlog |
| x402 provider   | Python 3.12, FastAPI                                          |
| Frontend        | Vue 3, Vite, Pinia, Tailwind CSS                              |
| Chain           | Kite Chain testnet (chainId 2368, EVM-compatible)             |
| Infra           | Railway (backend + x402-provider), Vercel (frontend)          |

---

## Reproducibility

```bash
# Full deploy + seed (interactive x402 token paste)
python scripts/deploy_and_seed.py

# Skip contract deploy (reuse existing CONTRACT_ADDRESS in .env)
python scripts/deploy_and_seed.py --skip-deploy

# Fully non-interactive (CI / automated demo)
python scripts/deploy_and_seed.py --skip-deploy --payment-token "eyJ..."
```

The script exits `0` on success and `1` on any failure, printing exactly which step failed and why.

---

## License

MIT
```bash
docker compose up --build
python scripts/deploy_and_seed.py
```

🖥️ Frontend (Vite dev server)	http://localhost:5173	✅ Running
🔌 Backend API / Swagger	http://localhost:8000/docs	✅ Running
⚙️ x402 Provider	http://localhost:9000	✅ Running
🔗 Anvil (local blockchain)	http://localhost:8545	✅ Running
🗄️ PostgreSQL	localhost:5432	✅ Running