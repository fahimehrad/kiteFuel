# 🪁 KiteFuel — Programmable Credit Layer for AI Agents

KiteFuel is an MVP monorepo that implements a **programmable, escrow-first credit layer**: a user creates a paid task, a borrower agent requests credit, a lender funds the escrow, the agent executes the task and delivers a report, the user pays, and the smart contract repays the lender first before releasing any remainder to the agent.

---

## End-to-End MVP Flow

```
1. User creates paid task
        │
        ▼
2. Borrower agent requests credit
        │
        ▼
3. Lender funds escrow (capital locked in KiteFuel contract)
        │
        ▼
4. Agent buys paid data (using credit drawn from escrow)
        │
        ▼
5. Agent generates report → delivers to user
        │
        ▼
6. User pays into the contract
        │
        ▼
7. Contract repays lender first (principal + fee)
        │
        ▼
8. Remainder released to agent
```

> **Escrow-first:** capital is never disbursed directly to the agent wallet. All funds flow through the KiteFuel smart contract so the lender is always protected.

---

## Monorepo Structure

```
kitefuel/
├── apps/
│   ├── frontend/       # Vue 3 + Vite + Tailwind CSS
│   ├── backend/        # Python FastAPI + SQLAlchemy + Alembic + web3.py
│   └── contracts/      # Solidity smart contracts (Foundry)
├── packages/
│   └── shared-types/   # Shared TypeScript types
├── docker-compose.yml
├── .env.example
└── README.md           ← you are here
```

---

## Running Locally

### Prerequisites

| Tool | Version |
|------|---------|
| Node.js | ≥ 18 |
| Python | ≥ 3.11 |
| Foundry (`forge`, `anvil`) | stable |
| Docker + Compose (optional) | ≥ 24 |

### 1 — Frontend
```bash
cd apps/frontend
npm install
npm run dev
# → http://localhost:5173
```

### 2 — Backend
```bash
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

### 3 — Contracts
```bash
cd apps/contracts
forge build
```

### 4 — Local EVM node
```bash
anvil
# starts a local Ethereum node on http://127.0.0.1:8545
# pre-funded test accounts are printed on startup
```

### 5 — Docker Compose
```bash
cp .env.example .env   # fill in values
docker compose up --build
# Compose will grow to include postgres and anvil services in later tasks
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy connection string (default: SQLite) |
| `ANVIL_RPC_URL` | Local or testnet RPC endpoint |
| `BACKEND_SIGNER_PRIVATE_KEY` | Private key used by the backend to sign transactions |
| `CONTRACT_ADDRESS` | Deployed KiteFuel contract address |
| `VITE_API_BASE_URL` | Backend base URL consumed by the frontend |

---

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"kitefuel-backend"}
```

---

## License
MIT
