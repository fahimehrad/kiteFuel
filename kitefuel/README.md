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

  Things you run yourself (Docker):       Things already running on the internet:
  ─────────────────────────────           ──────────────────────────────────────                                                                                                                                                                                                                                          
  ✅ Backend (FastAPI)                    ✅ https://facilitator.pieverse.io                                                                                                                                                                                                                                                
  ✅ x402-provider                        ✅ https://rpc-testnet.gokite.ai (Kite RPC)                                                                                                                                                                                                                                       
  ✅ Frontend (Vue)                       ✅ https://faucet.gokite.ai (free tokens)                                                                                                                                                                                                                                         
  ✅ PostgreSQL                           ✅ https://api.coingecko.com (price data)                                                                                                                                                                                                                                       ──
  ✅ Smart contract (deploy once)    



 How It All Connects in Your Project
                                                                                                                                                                                                                                                                                                                          
  ┌─────────────────────────────────────────────────────────────┐
  │                    YOUR PROJECT FLOW                        │                                                                                                                                                                                                                                                         
  │                                                             │
  │  1. User creates a task in the Vue frontend                 │                                                                                                                                                                                                                                                         
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  2. Backend (FastAPI) requests credit                       │                                                                                                                                                                                                                                                         
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  3. Smart contract on Kite testnet locks funds (escrow)     │
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  4. Backend calls x402-provider to buy market data          │
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  5. x402-provider says "pay me first" (HTTP 402)            │
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  6. Kite Passport signs the payment → X-PAYMENT token       │
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  7. Backend retries with X-PAYMENT token                    │
  │         ↓                                                   │                                                                                                                                                                                                                                                         
  │  8. Pieverse facilitator moves Test-USDT on Kite testnet    │                                                                                                                                                                                                                                                         
  │         ↓                                                   │
  │  9. x402-provider returns BTC market data + AI report       │                                                                                                                                                                                                                                                         
  │         ↓                                                   │
  │  10. Smart contract repays lender, releases remainder       │                                                                                                                                                                                                                                                         
  └─────────────────────────────────────────────────────────────┘
                                                                                                                                                                                                                                                                                                                          
  ---             
  What You Need To Run It                                                                                                                                                                                                                                                                                                 
                         
  ┌──────┬─────────────────────────────────┬────────────────────────────────────────────┐
  │ Step │              What               │                    How                     │                                                                                                                                                                                                                                 
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤
  │ 1    │ A wallet on Kite testnet        │ MetaMask + add Kite testnet                │                                                                                                                                                                                                                                 
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤
  │ 2    │ Testnet KITE tokens (for gas)   │ Free from faucet.gokite.ai                 │                                                                                                                                                                                                                                 
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤                                                                                                                                                                                                                                 
  │ 3    │ Testnet USDT (for x402 payment) │ Kite Passport gives you test tokens        │                                                                                                                                                                                                                                 
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤                                                                                                                                                                                                                                 
  │ 4    │ Deploy the smart contract       │ Run forge script (one time)                │
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤                                                                                                                                                                                                                                 
  │ 5    │ Start services                  │ docker compose up --build                  │
  ├──────┼─────────────────────────────────┼────────────────────────────────────────────┤                                                                                                                                                                                                                                 
  │ 6    │ Get X-PAYMENT token             │ Kite Passport (I can do this for you here) │
  └──────┴─────────────────────────────────┴────────────────────────────────────────────┘                                                                                                                                                                                                                                 
   
  The step that's interactive is step 6 — when the deploy script pauses and says "paste your X-PAYMENT token." That's where Kite Passport comes in, and I can help generate that token for you as part of running the demo.                                                                                               
                  
  Do you have a wallet already, or should we start from creating one?                                                                                                                                                                                                                                                     
                  
  Which Is Better For Your Project?
                                   
  ┌────────────────────────────┬────────────────────┬───────────────┐
  │                            │ Off-chain matching │ On-chain pool │                                                                                                                                                                                                                                                     
  ├────────────────────────────┼────────────────────┼───────────────┤
  │ Speed                      │ Fast (ms)          │ Fast (one tx) │                                                                                                                                                                                                                                                     
  ├────────────────────────────┼────────────────────┼───────────────┤
  │ Lender needs to be online? │ No                 │ No            │                                                                                                                                                                                                                                                     
  ├────────────────────────────┼────────────────────┼───────────────┤                                                                                                                                                                                                                                                     
  │ Human approval per loan?   │ No                 │ No            │                                                                                                                                                                                                                                                     
  ├────────────────────────────┼────────────────────┼───────────────┤                                                                                                                                                                                                                                                     
  │ Truly agentic?             │ Yes                │ Yes           │
  ├────────────────────────────┼────────────────────┼───────────────┤                                                                                                                                                                                                                                                     
  │ Complexity                 │ Low                │ Higher        │
  └────────────────────────────┴────────────────────┴───────────────┘                                                                                                                                                                                                                                                     
                  
  Both solve your problem. The agent doesn't wait for a human — it finds a pre-existing offer and the money moves automatically.                                                                                                                                                                                          
   
  ---                                                                                                                                                                                                                                                                                                                     
  What Your Demo Does vs What Could Be Real
                                                                                                                                                                                                                                                                                                                          
  Current demo (fake):
    Agent requests credit → backend just makes up a lender → no real money moves from lender                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                                          
  Real version (simple fix):                                                                                                                                                                                                                                                                                              
    Lender signs up once → deposits KITE into your app                                                                                                                                                                                                                                                                    
    Agent requests credit → contract pulls from lender's deposit → immediate                                                                                                                                                                                                                                              
   
    The lender isn't online. They already said yes in advance by depositing.                                                                                                                                                                                                                                              
                  
  The key insight is: "approving" in the agentic world doesn't mean clicking a button in real-time. It means depositing money into a contract and setting your rules upfront. After that, everything is automatic.     
  
 ---                                                                                                                                                                                                                                                                                                                     
  This Is Just Normal Lending Risk
                                                                                                                                                                                                                                                                                                                          
  Agent borrows, strategy fails, no revenue generated
  → Lender loses their money                                                                                                                                                                                                                                                                                              
  → This is the lender's risk in exchange for the fee they charge
                                                                                                                                                                                                                                                                                                                          
  Same as a bank lending to a restaurant that goes bankrupt. The bank knew it was possible. That's why they charged interest.                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                                          
  ---                                                                                                                                                                                                                                                                                                                     
  How Real Systems Manage This Risk
                                   
  1. Credit scoring
  Lenders only lend to agents with a good track record.                                                                                                                                                                                                                                                                   
  Agent has run 100 strategies → 95 were profitable                                                                                                                                                                                                                                                                       
  → Lender is willing to lend at low fee                                                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                                          
  New agent with no history                                                                                                                                                                                                                                                                                               
  → Lender charges higher fee or refuses                                                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                                          
  2. Partial collateral                                                                                                                                                                                                                                                                                                   
  Agent doesn't need 100% collateral (which would defeat the purpose), but puts up something:
  Agent has 0.005 KITE of its own                                                                                                                                                                                                                                                                                         
  → puts it in escrow alongside lender's 0.01 KITE
  → if strategy fails, lender gets the 0.005 first                                                                                                                                                                                                                                                                        
  → lender's max loss is cut in half              
                                                                                                                                                                                                                                                                                                                          
  3. Loan size limits
  Lender caps how much they lend per agent or per task:                                                                                                                                                                                                                                                                   
  New agent → max loan 0.01 KITE                                                                                                                                                                                                                                                                                          
  Trusted agent with track record → max loan 10 KITE                                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                                                                          
  4. Insurance pools                                                                                                                                                                                                                                                                                                      
  A separate pool of capital that covers lender losses in exchange for a small premium — like DeFi insurance (Nexus Mutual).                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                                          
  ---             
  This Risk Is Actually The Point Of Your Project                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                                          
  Without KiteFuel:
    Agent has no capital → can't do anything → stuck                                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                                                                          
  With KiteFuel:
    Lender takes calculated risk → agent can operate                                                                                                                                                                                                                                                                      
    If agent succeeds → both win                                                                                                                                                                                                                                                                                          
    If agent fails → lender loses (knew the risk, charged fee for it)                                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                                                                                                          
  This is venture capital logic applied to AI agents at micro scale. VCs know most startups fail. They still invest because the winners cover all the losses.                                                                                                                                                             
                                                                                                                                                                                                                                                                                                                          
  ---                                                                                                                                                                                                                                                                                                                     
  So Your Project Makes Complete Sense When Framed As:
                                                                                                                                                                                                                                                                                                                          
  ▎ "A credit market where lenders bet on AI agents, earning fees when agents succeed and absorbing losses when they fail — with the smart contract guaranteeing that IF revenue exists, lenders are always paid first."
                                                                                                                                                                                                                                                                                                                          
  The lender risk is a feature, not a bug. It's what makes the market work.           
  



 ######
The Biggest Problems Right Now                                                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                                          
  1. The demo breaks at step 5 — it pops up a modal asking you to manually paste an X-PAYMENT token. A judge watching this demo will see it freeze and not know what to do. This kills the demo.                                                                                                                          
                                                                                                                                                                                                                                                                                                                          
  2. The generated report is never shown — the AI report is stored in the database but the UI never displays it. The most impressive output of the whole system is invisible.                                                                                                                                             
                                                                                                                                                                                                                                                                                                                          
  3. The narrative is weak — "user pays after seeing report" doesn't make sense economically (as we discussed). Judges who think about it will have the same question you had.                                                                                                                                            
                  
  ---                                                                                                                                                                                                                                                                                                                     
  What To Fix, In Priority Order
                                                                                                                                                                                                                                                                                                                          
  Priority 1 — Make It Actually Run (Infrastructure)
                                                                                                                                                                                                                                                                                                                          
  Before anything else, you need wallets and testnet tokens. Nothing matters until this works.                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                          
  Priority 2 — Automate The X-PAYMENT Token (Kills Demo If Broken)                                                                                                                                                                                                                                                        
                  
  Right now the frontend pauses and shows a modal waiting for you to paste a token. For a demo this is fatal. The backend should get the X-PAYMENT token automatically via Kite Passport — no human paste needed.                                                                                                         
                  
  Priority 3 — Show The Report In The UI                                                                                                                                                                                                                                                                                  
                  
  The Claude-generated market brief should be displayed beautifully after step 6. Right now judges never see the actual output of the agent.                                                                                                                                                                              
   
  Priority 4 — Reframe The Narrative                                                                                                                                                                                                                                                                                      
                  
  Change "user pays" to "agent earns automatically." One line change in the demo script + one sentence on the UI makes the concept make sense.                                                                                                                                                                            
                  
  Priority 5 — Show Lender Economics Visually                                                                                                                                                                                                                                                                             
                  
  Add a simple panel showing lender wallet balance before → after. Makes the credit concept tangible for judges.                                                                                                                                                                                                          
   
  ---                                                                                                                                                                                                                                                                                                                     
  Which of these do you want to work on first?
                                                                                                                                                                                                                                                                                                                          
  The order I'd recommend: infrastructure → automate X-PAYMENT → show report → reframe narrative.
                                                                                                                                                                                                                                                                                                                          
  The first two are blockers — the demo literally doesn't work without them. The last two are what impresses judges.  
  

                                                                                                                                                                                                                                                                                                                          
  So the full sequence is:     
docker compose down && docker compose up --build 

  First time:    docker compose up --build                                                                                                                                                                                                                                                                                
                python scripts/deploy_and_seed.py         ← deploys + seeds
                                                                                                                                                                                                                                                                                                                          
  Every time after:
                 docker compose up                                                                                                                                                                                                                                                                                        
                 python scripts/deploy_and_seed.py --skip-deploy   ← just seeds