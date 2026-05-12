"""
KiteFuel Agentic Chat — POST /agent/chat

Streams Server-Sent Events as Claude autonomously:
  1. Calls borrow_credit()     — creates task + escrow on-chain
  2. Calls get_market_data()   — x402 purchase via X402Client (DEMO_MODE)
  3. Calls repay_loan()        — generate-report + user-pay + settle on-chain

Each SSE line: data: <JSON>\n\n
Event shapes:
  {"type": "text",        "content": "..."}
  {"type": "tool_call",  "name": "...", "input": {...}}
  {"type": "tool_result","name": "...", "result": {...}}
  {"type": "error",      "content": "..."}
  {"type": "done"}
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import anthropic
import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import (
    CreditOffer,
    DataPurchase,
    EscrowPosition,
    RepaymentRecord,
    StateTransition,
    Task,
)
from services.contract_service import ContractError, ContractService
from services.x402_client import X402Client

router = APIRouter(prefix="/agent", tags=["agent"])
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirrors tasks.py)
# ---------------------------------------------------------------------------

_DEMO_LENDER   = os.getenv("DEMO_LENDER_ADDRESS",  "0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
_DEMO_BORROWER = os.getenv("DEMO_BORROWER_ADDRESS", "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC")
_CREDIT_WEI    = int(0.01  * 10**18)
_REPAY_WEI     = int(0.011 * 10**18)
_REVENUE_WEI   = int(0.012 * 10**18)
_X402_SYMBOL   = "BTC"
_X402_AMOUNT   = 5.0

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _task_id_to_bytes32(task_id: str) -> bytes:
    raw = task_id.encode("utf-8")
    return raw[:32].ljust(32, b"\x00")


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


# ---------------------------------------------------------------------------
# Tool implementations  (sync — called via asyncio.to_thread where needed)
# ---------------------------------------------------------------------------

def _db_borrow_credit(db: Session) -> dict:
    """
    DB side of borrow_credit:
    Creates Task → CreditOffer → credit_approved state, returns task_id.
    (The on-chain fund step is done separately so we can stay async.)
    """
    task_id = str(uuid.uuid4())
    now = _utcnow()

    task = Task(id=task_id, state="task_created", created_at=now, updated_at=now)
    db.add(task)
    db.add(StateTransition(task_id=task_id, from_state="", to_state="task_created",
                           timestamp=now, note="Agent task created"))

    # credit_requested
    offer = CreditOffer(
        task_id=task_id,
        lender_address=_DEMO_LENDER,
        credit_amount=_CREDIT_WEI / 10**18,
        repay_amount=_REPAY_WEI / 10**18,
    )
    db.add(offer)
    task.state = "credit_requested"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="task_created",
                           to_state="credit_requested", timestamp=_utcnow()))

    # credit_approved
    task.state = "credit_approved"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="credit_requested",
                           to_state="credit_approved", timestamp=_utcnow()))

    db.commit()
    db.refresh(task)
    return task_id


def _db_mark_funds_locked(db: Session, task_id: str, tx_hash: str, contract_address: str) -> None:
    task = db.get(Task, task_id)
    db.add(EscrowPosition(
        task_id=task_id,
        contract_address=contract_address,
        tx_hash=tx_hash,
        state="funds_locked",
    ))
    task.state = "funds_locked"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="credit_approved",
                           to_state="funds_locked", timestamp=_utcnow(), note=f"tx={tx_hash}"))
    db.commit()


def _db_mark_data_purchased(db: Session, task_id: str, market_data: dict) -> None:
    task = db.get(Task, task_id)
    full_report = market_data.get("report") or market_data.get("summary", "")
    result_summary = (
        f"[x402 | {market_data.get('data_provider', 'KiteFuel Market Data')}] "
        f"{market_data.get('symbol', _X402_SYMBOL)} ({market_data.get('trend', 'unknown')})\n\n"
        f"{full_report}"
    )
    db.add(DataPurchase(
        task_id=task_id,
        provider=market_data.get("data_provider", "KiteFuel Market Data (x402 — Agent)"),
        amount=_X402_AMOUNT,
        result_summary=result_summary,
        payment_token="agent-demo-mode",
        purchased_at=_utcnow(),
    ))
    task.state = "data_purchased"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="funds_locked",
                           to_state="data_purchased", timestamp=_utcnow(),
                           note=f"x402 agent symbol={_X402_SYMBOL}"))
    db.commit()


def _db_generate_report(db: Session, task_id: str) -> None:
    task = db.get(Task, task_id)
    latest = (db.query(DataPurchase)
               .filter(DataPurchase.task_id == task_id)
               .order_by(DataPurchase.id.desc())
               .first())
    if latest:
        latest.result_summary = f"[REPORT GENERATED] {latest.result_summary}"
    task.state = "result_generated"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="data_purchased",
                           to_state="result_generated", timestamp=_utcnow()))
    db.commit()


def _db_user_pay(db: Session, task_id: str, tx_hash: str) -> None:
    task = db.get(Task, task_id)
    task.state = "user_paid"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="result_generated",
                           to_state="user_paid", timestamp=_utcnow(),
                           note=f"revenue_wei={_REVENUE_WEI} tx={tx_hash}"))
    db.commit()


def _db_settle(db: Session, task_id: str, tx_hash: str) -> dict:
    task = db.get(Task, task_id)
    lender_paid = _REPAY_WEI / 10**18
    remainder   = max(0.0, _REVENUE_WEI / 10**18 - lender_paid)
    db.add(RepaymentRecord(
        task_id=task_id,
        lender_paid=lender_paid,
        remainder_released=remainder,
        settled_at=_utcnow(),
    ))
    task.state = "lender_repaid"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="user_paid",
                           to_state="lender_repaid", timestamp=_utcnow(), note=f"tx={tx_hash}"))
    task.state = "task_closed"
    task.updated_at = _utcnow()
    db.add(StateTransition(task_id=task_id, from_state="lender_repaid",
                           to_state="task_closed", timestamp=_utcnow()))
    db.commit()
    return {"lender_paid": lender_paid, "remainder": remainder}


# ---------------------------------------------------------------------------
# High-level async tool functions (called by the agent loop)
# ---------------------------------------------------------------------------

async def tool_borrow_credit(db: Session) -> dict:
    """Create task + escrow on-chain, advance state to funds_locked."""
    try:
        task_id = await asyncio.to_thread(_db_borrow_credit, db)
    except Exception as exc:
        return {"error": f"DB error during borrow_credit: {exc}"}

    # On-chain: create escrow + fund — sync, so run in thread
    try:
        def _fund():
            svc = ContractService()
            tb32 = _task_id_to_bytes32(task_id)
            already_exists = svc.contract.functions.exists(tb32).call()
            if not already_exists:
                svc.create_task_escrow(
                    task_id=tb32,
                    borrower=_DEMO_BORROWER,
                    lender=_DEMO_LENDER,
                    credit_amount_wei=_CREDIT_WEI,
                    repay_amount_wei=_REPAY_WEI,
                )
            tx_hash = svc.fund_credit(task_id=tb32, value_wei=_CREDIT_WEI)
            return tx_hash, svc.contract_address

        tx_hash, contract_address = await asyncio.to_thread(_fund)
        await asyncio.to_thread(_db_mark_funds_locked, db, task_id, tx_hash, contract_address)
    except ContractError as exc:
        return {"error": f"Contract error: {exc}"}
    except Exception as exc:
        return {"error": f"Unexpected error funding escrow: {exc}"}

    return {
        "task_id": task_id,
        "credit_kite": _CREDIT_WEI / 10**18,
        "tx_hash": tx_hash,
        "state": "funds_locked",
    }


async def tool_get_market_data(symbol: str, task_id: str | None, db: Session) -> dict:
    """Purchase market data via X402Client (DEMO_MODE returns mock data)."""
    try:
        market_data = await X402Client().complete_purchase(symbol.upper())
    except Exception as exc:
        return {"error": f"x402 purchase failed: {exc}"}

    if task_id:
        try:
            await asyncio.to_thread(_db_mark_data_purchased, db, task_id, market_data)
        except Exception as exc:
            logger.warning("agent_data_purchase_db_error", task_id=task_id, error=str(exc))
            # Don't fail — market data was fetched successfully

    return {
        "symbol": market_data.get("symbol"),
        "price_usd": market_data.get("price_usd"),
        "trend": market_data.get("trend"),
        "summary": market_data.get("summary"),
        "report": market_data.get("report", ""),
        "data_provider": market_data.get("data_provider"),
    }


async def tool_repay_loan(task_id: str, db: Session) -> dict:
    """Advance state through generate-report → user-pay → settle on-chain."""
    try:
        await asyncio.to_thread(_db_generate_report, db, task_id)
    except Exception as exc:
        return {"error": f"generate-report DB error: {exc}"}

    try:
        def _register():
            svc = ContractService()
            return svc.register_revenue(
                task_id=_task_id_to_bytes32(task_id),
                value_wei=_REVENUE_WEI,
            )
        pay_tx = await asyncio.to_thread(_register)
        await asyncio.to_thread(_db_user_pay, db, task_id, pay_tx)
    except ContractError as exc:
        return {"error": f"registerRevenue contract error: {exc}"}
    except Exception as exc:
        return {"error": f"user-pay error: {exc}"}

    try:
        def _settle():
            svc = ContractService()
            return svc.settle(task_id=_task_id_to_bytes32(task_id))
        settle_tx = await asyncio.to_thread(_settle)
        repayment = await asyncio.to_thread(_db_settle, db, task_id, settle_tx)
    except ContractError as exc:
        return {"error": f"settle contract error: {exc}"}
    except Exception as exc:
        return {"error": f"settle error: {exc}"}

    return {
        "tx_hash": settle_tx,
        "lender_paid_kite": repayment["lender_paid"],
        "remainder_kite": repayment["remainder"],
        "state": "task_closed",
    }


# ---------------------------------------------------------------------------
# Claude tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "borrow_credit",
        "description": (
            "Borrow credit from a KiteFuel lender. Creates an on-chain escrow and locks 0.01 KITE "
            "as your credit line. Call this before buying any paid market data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_market_data",
        "description": (
            "Buy a paid market intelligence brief for the given crypto symbol (e.g. BTC, ETH, SOL) "
            "using x402 protocol. Costs credit from your active loan. Returns price, trend, and a "
            "research report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Crypto symbol e.g. BTC, ETH, SOL"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "repay_loan",
        "description": (
            "Repay the lender and close the loan. Call this after you have generated your "
            "recommendation. Settles the on-chain escrow."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task_id returned by borrow_credit"},
            },
            "required": ["task_id"],
        },
    },
]

SYSTEM_PROMPT = """\
You are an autonomous AI agent powered by KiteFuel — a programmable credit \
protocol on Kite Chain. You can borrow credit to pay for market intelligence \
APIs (x402 protocol), then repay the lender from the value you generate.

Rules:
- If you need to call paid APIs, ALWAYS call borrow_credit first.
- After buying data, analyze it and form a recommendation.
- ALWAYS call repay_loan at the end if you borrowed.
- If the user asks something that doesn't need paid data, just answer directly.
- Be concise and specific in your final answer.\
"""

# ---------------------------------------------------------------------------
# Agent loop (SSE generator)
# ---------------------------------------------------------------------------

async def _agent_stream(message: str, db: Session) -> AsyncGenerator[str, None]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield _sse({"type": "error", "content": "ANTHROPIC_API_KEY is not set"})
        yield _sse({"type": "done"})
        return

    client = anthropic.Anthropic(api_key=api_key)
    messages: list[dict] = [{"role": "user", "content": message}]

    # Track the current task_id across tool calls
    current_task_id: str | None = None

    try:
        while True:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=messages,
            )

            # Collect assistant content blocks and stream text deltas
            assistant_content: list[dict] = []
            tool_uses: list[dict] = []

            for block in response.content:
                if block.type == "text":
                    yield _sse({"type": "text", "content": block.text})
                    assistant_content.append({"type": "text", "text": block.text})

                elif block.type == "tool_use":
                    tool_uses.append(block)
                    yield _sse({"type": "tool_call", "name": block.name, "input": block.input})
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            # Append the full assistant turn
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn" or not tool_uses:
                break

            # Execute each tool and collect results
            tool_results: list[dict] = []
            for block in tool_uses:
                name   = block.name
                inputs = block.input or {}

                if name == "borrow_credit":
                    result = await tool_borrow_credit(db)
                    if "task_id" in result:
                        current_task_id = result["task_id"]

                elif name == "get_market_data":
                    symbol = inputs.get("symbol", _X402_SYMBOL)
                    result = await tool_get_market_data(symbol, current_task_id, db)

                elif name == "repay_loan":
                    tid = inputs.get("task_id") or current_task_id
                    if not tid:
                        result = {"error": "No task_id available — call borrow_credit first"}
                    else:
                        result = await tool_repay_loan(tid, db)

                else:
                    result = {"error": f"Unknown tool: {name}"}

                yield _sse({"type": "tool_result", "name": name, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            # Feed tool results back to Claude
            messages.append({"role": "user", "content": tool_results})

    except anthropic.APIError as exc:
        yield _sse({"type": "error", "content": f"Anthropic API error: {exc}"})
    except Exception as exc:
        logger.exception("agent_stream_error", error=str(exc))
        yield _sse({"type": "error", "content": f"Agent error: {exc}"})

    yield _sse({"type": "done"})


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/chat", summary="Agentic chat — streams SSE")
async def agent_chat(body: ChatRequest, db: Session = Depends(get_db)):
    """
    POST /agent/chat
    Body: { "message": "..." }
    Returns: text/event-stream of JSON SSE events.
    """
    async def generate():
        async for chunk in _agent_stream(body.message, db):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
        },
    )
