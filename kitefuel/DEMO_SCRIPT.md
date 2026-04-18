# KiteFuel — 90-Second Demo Script

> **Presenter notes:** open the live demo at https://kitefuel.vercel.app before starting.  
> Have a valid X-PAYMENT token copied to clipboard.  
> Keep the KiteScan tab ready in a second browser tab.

---

## Spoken Script

### `0:00` — Open

> "KiteFuel gives AI agents programmable credit — borrow, execute, repay, all enforced by a smart contract on Kite Chain. Let me show you the full lifecycle in ninety seconds."

---

### `0:10` — Start the demo

> "I'm clicking **Run Full Demo**. The frontend talks to our FastAPI backend, which is connected to KiteFuelEscrow deployed on Kite Chain testnet."

*Click **Run Full Demo** in the DemoPanel.*

> "Step one: task created. Step two: the borrower agent requests credit. Step three: lender approves and the backend calls `fundCredit` on-chain — 0.01 KITE is now locked in escrow."

*Watch steps 1–3 complete automatically.*

---

### `0:25` — Fund confirmed

> "The escrow is funded. Notice the KiteScan link — that's a real on-chain transaction, verifiable right now."

*Point to the transaction hash / explorer link appearing in the UI.*

---

### `0:40` — x402 payment gate

> "Step four: the agent calls our market-data service. The service responds HTTP 402 — payment required. The demo pauses here."

*X402PaymentModal appears on screen.*

> "This is the x402 payment gate. The agent needs an X-PAYMENT token to proceed. In production that token comes from Kite Passport or an MCP agent. I've got one pre-prepared."

---

### `0:50` — Paste token

> "I'm pasting the X-PAYMENT token now. The backend forwards it to the x402 provider, which sends it to the Pieverse facilitator. The facilitator validates it and settles the payment on Kite Chain."

*Paste the token into the modal and confirm.*

---

### `1:05` — Purchase confirmed, report generated

> "Payment confirmed. The agent now has the market data — BTC price, trend, summary — all purchased with a cryptographically verified on-chain payment. Step six: report generated."

*Watch steps 6–7 complete.*

---

### `1:15` — Settle on-chain

> "Step seven: the user registers revenue. Step eight: settle. The contract pays the lender first — principal plus fee — and releases the remainder. No human approval. No manual transfer."

*Watch settle complete.*

---

### `1:25` — KiteScan attestations

> "Click the KiteScan link. Every action — fund, revenue, repayment — is an emitted event on Kite Chain. The lender can verify repayment without trusting the backend."

*Switch to KiteScan tab showing the transaction.*

---

### `1:30` — Close

> "KiteFuel: programmable, escrow-first credit for AI agents — fully on-chain, fully verifiable on Kite."

---

## Judge Q&A Prep

---

**Q1: How is this Kite-native?**

> Every trust-sensitive step runs on Kite Chain: escrow funding, x402 settlement via Pieverse facilitator, revenue registration, and lender repayment. Attestations are KiteScan-verifiable events emitted by `KiteFuelEscrow`. The payment token is Test USDT on Kite Chain; gas is KITE native token. Nothing in the credit lifecycle touches another chain.

---

**Q2: What if the agent overspends?**

> The `KiteFuelEscrow` contract enforces an `OverSpendLimit` check on every `recordSpend` call. If cumulative spending would exceed the approved credit amount the transaction reverts on-chain — the agent cannot draw more than the lender committed, regardless of what the backend instructs.

---

**Q3: Why would a lender fund this?**

> Two on-chain guarantees make this attractive. First, the `settle` function pays the lender — principal plus fee — before releasing any remainder to the borrower; the lender is structurally first in line. Second, the `creditAmount` cap bounds the lender's exposure: the borrower cannot spend more than the approved amount, so maximum loss is known at the time of funding.

---

**Q4: Why x402 instead of subscriptions?**

> x402 is per-task and trustless: each purchase requires a cryptographically signed token settled on-chain by the Pieverse facilitator. There is no recurring billing relationship, no API key that can be leaked, and no off-chain invoice to reconcile. An AI agent can autonomously acquire and use an X-PAYMENT token for exactly one task without any persistent subscription or human-held credential.
