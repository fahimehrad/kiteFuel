"""
KiteFuel task lifecycle routes.

Every mutating endpoint that touches an external system (smart contract or
data provider) follows the strict order:
  1. execute external side-effect
  2. if successful → apply state transition
  3. persist DB changes
  4. return response
"""

import os
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Task,
    CreditOffer,
    EscrowPosition,
    DataPurchase,
    RepaymentRecord,
    StateTransition,
)
from schemas import ConfirmPurchaseRequest
from services.state_machine import transition, next_action, InvalidTransition
from services.contract_service import ContractService, ContractError
from services.x402_client import X402Client, X402Error, X402PaymentRejected, ConfigurationError

router = APIRouter(prefix="/tasks", tags=["tasks"])

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Demo constants
# ---------------------------------------------------------------------------

_DEMO_LENDER    = os.getenv("DEMO_LENDER_ADDRESS",   "0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
_DEMO_BORROWER  = os.getenv("DEMO_BORROWER_ADDRESS",  "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC")
_DEMO_PROVIDER  = os.getenv("DEMO_PROVIDER_ADDRESS",  "0x90F79bf6EB2c4f870365E785982E1f101E93b906")

# Demo: credit_amount = 0.01 ETH, repay_amount = 0.011 ETH
_CREDIT_WEI = int(0.01  * 10**18)
_REPAY_WEI  = int(0.011 * 10**18)
_REVENUE_WEI = int(0.012 * 10**18)   # demo revenue > repay so lender is whole

_KITE_EXPLORER_BASE = "https://testnet.kitescan.ai/tx"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _kite_tx_url(tx_hash: str) -> str:
    """Return a KiteScan explorer URL for the given transaction hash."""
    return f"{_KITE_EXPLORER_BASE}/{tx_hash}"


def _log_event(event: str, **kwargs) -> None:
    """Emit one structured JSON log entry at INFO level."""
    logger.info(event, timestamp=_iso_now(), **kwargs)


def _log_warning(event: str, **kwargs) -> None:
    """Emit one structured JSON log entry at WARNING level."""
    logger.warning(event, timestamp=_iso_now(), **kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _task_id_to_bytes32(task_id: str) -> bytes:
    """Encode a UUID-style task_id string to a 32-byte value for the contract."""
    raw = task_id.encode("utf-8")
    return raw[:32].ljust(32, b"\x00")


def _get_task_or_404(task_id: str, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def _safe_transition(task: Task, to_state: str) -> None:
    """Apply state_machine.transition, raising 409 on invalid transition."""
    try:
        transition(task.state, to_state)
    except InvalidTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": str(exc), "current_state": task.state},
        )


def _add_state_transition(db: Session, task_id: str, from_state: str, to_state: str, note: str = "") -> None:
    db.add(StateTransition(
        task_id=task_id,
        from_state=from_state,
        to_state=to_state,
        timestamp=_utcnow(),
        note=note or None,
    ))


def _task_response(task: Task, message: str = "") -> dict:
    return {
        "task": {
            "id": task.id,
            "state": task.state,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        },
        "next_action": next_action(task.state),
        "message": message,
    }


def _task_detail_response(task: Task, message: str = "") -> dict:
    base = _task_response(task, message)
    base["credit_offers"] = [
        {
            "id": o.id,
            "lender_address": o.lender_address,
            "credit_amount": o.credit_amount,
            "repay_amount": o.repay_amount,
        }
        for o in task.credit_offers
    ]
    base["escrow_positions"] = [
        {
            "id": e.id,
            "contract_address": e.contract_address,
            "tx_hash": e.tx_hash,
            "state": e.state,
        }
        for e in task.escrow_positions
    ]
    base["data_purchases"] = [
        {
            "id": d.id,
            "provider": d.provider,
            "amount": d.amount,
            "result_summary": d.result_summary,
            "purchased_at": d.purchased_at.isoformat() if d.purchased_at else None,
        }
        for d in task.data_purchases
    ]
    base["repayment_records"] = [
        {
            "id": r.id,
            "lender_paid": r.lender_paid,
            "remainder_released": r.remainder_released,
            "settled_at": r.settled_at.isoformat() if r.settled_at else None,
        }
        for r in task.repayment_records
    ]
    base["state_transitions"] = [
        {
            "id": s.id,
            "from_state": s.from_state,
            "to_state": s.to_state,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "note": s.note,
        }
        for s in task.state_transitions
    ]
    return base


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", summary="Create a new task", status_code=201)
def create_task(db: Session = Depends(get_db)):
    """Create a new KiteFuel task in the 'task_created' state."""
    task_id = str(uuid.uuid4())
    now = _utcnow()
    task = Task(id=task_id, state="task_created", created_at=now, updated_at=now)
    db.add(task)
    _add_state_transition(db, task_id, "", "task_created", note="Task created")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("task_create_db_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    _log_event("task_created", task_id=task_id, state="task_created")
    return _task_response(task, "Task created")


@router.post("/{task_id}/request-credit", summary="Request credit for a task")
def request_credit(task_id: str, db: Session = Depends(get_db)):
    """Transition the task from 'task_created' to 'credit_requested' and create a default CreditOffer."""
    task = _get_task_or_404(task_id, db)
    _safe_transition(task, "credit_requested")

    offer = CreditOffer(
        task_id=task_id,
        lender_address=_DEMO_LENDER,
        credit_amount=_CREDIT_WEI / 10**18,
        repay_amount=_REPAY_WEI / 10**18,
    )
    db.add(offer)
    prev_state = task.state
    task.state = "credit_requested"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "credit_requested")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("request_credit_db_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    _log_event("credit_requested", task_id=task_id, state="credit_requested")
    return _task_response(task, "Credit requested")


@router.post("/{task_id}/approve-credit", summary="Approve the credit offer")
def approve_credit(task_id: str, db: Session = Depends(get_db)):
    """Transition the task from 'credit_requested' to 'credit_approved'."""
    task = _get_task_or_404(task_id, db)
    _safe_transition(task, "credit_approved")

    prev_state = task.state
    task.state = "credit_approved"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "credit_approved")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("approve_credit_db_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    _log_event("credit_approved", task_id=task_id, state="credit_approved")
    return _task_response(task, "Credit approved")


@router.post("/{task_id}/fund", summary="Fund the escrow on-chain")
def fund(task_id: str, db: Session = Depends(get_db)):
    """
    Fund the escrow contract.
    Calls fundCredit on the smart contract FIRST; only updates DB state on success.
    """
    task = _get_task_or_404(task_id, db)
    if task.state != "credit_approved":
        raise HTTPException(
            status_code=409,
            detail={"error": "Task must be in 'credit_approved' state to fund", "current_state": task.state},
        )

    offer = db.query(CreditOffer).filter(CreditOffer.task_id == task_id).first()
    if offer is None:
        raise HTTPException(status_code=409, detail="No CreditOffer found for this task")

    # 1. External side-effects first: create escrow on-chain (idempotent), then fund it
    try:
        svc = ContractService()
        task_bytes32 = _task_id_to_bytes32(task_id)
        # Only create the on-chain escrow if it doesn't already exist (retry-safe)
        already_exists = svc.contract.functions.exists(task_bytes32).call()
        if not already_exists:
            svc.create_task_escrow(
                task_id=task_bytes32,
                borrower=_DEMO_BORROWER,
                lender=_DEMO_LENDER,
                credit_amount_wei=_CREDIT_WEI,
                repay_amount_wei=_REPAY_WEI,
            )
        tx_hash = svc.fund_credit(
            task_id=task_bytes32,
            value_wei=_CREDIT_WEI,
        )
    except ContractError as exc:
        _log_warning("fund_contract_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Contract call failed: {exc}")
    except Exception as exc:
        _log_warning("fund_unexpected_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Unexpected error during fund: {exc}")

    # 2. Validate transition, then persist DB state
    _safe_transition(task, "funds_locked")
    prev_state = task.state
    escrow = EscrowPosition(
        task_id=task_id,
        contract_address=svc.contract_address,
        tx_hash=tx_hash,
        state="funds_locked",
    )
    db.add(escrow)
    task.state = "funds_locked"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "funds_locked", note=f"tx={tx_hash}")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("fund_db_error", task_id=task_id, tx_hash=tx_hash, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    amount_kite = f"{_CREDIT_WEI / 10**18:.6f}".rstrip("0").rstrip(".")
    _log_event(
        "escrow_funded",
        task_id=task_id,
        state="funds_locked",
        tx_hash=tx_hash,
        amount_kite=amount_kite,
        kite_explorer_url=_kite_tx_url(tx_hash),
    )
    return _task_response(task, f"Escrow funded (tx={tx_hash})")


# ---------------------------------------------------------------------------
# x402 demo constants
# ---------------------------------------------------------------------------

_X402_SYMBOL = "BTC"                # symbol used for all demo x402 market-data purchases
_X402_AMOUNT = 5.0                  # display amount in payment token units (Test USDT, 18 dec)


@router.post("/{task_id}/buy-data", summary="Initiate x402 data purchase — returns payment requirements")
async def buy_data(task_id: str, db: Session = Depends(get_db)):
    """
    Step 1 of the two-step x402 buy-data flow.

    Calls the x402 provider to retrieve payment requirements (HTTP 402).
    Does NOT advance task state — the client must complete the purchase via
    POST /tasks/{id}/buy-data/confirm with a real X-PAYMENT token.

    Returns:
        {payment_required: true, requirements: {...}, message: "..."}
    """
    task = _get_task_or_404(task_id, db)
    if task.state != "funds_locked":
        raise HTTPException(
            status_code=409,
            detail={"error": "Task must be in 'funds_locked' state to buy data", "current_state": task.state},
        )

    # Ask the x402 provider what it needs — backend does NOT sign or generate a token
    try:
        client = X402Client()
        requirements = await client.request_payment_requirements(_X402_SYMBOL)
    except ConfigurationError as exc:
        _log_warning(
            "x402_configuration_error",
            task_id=task_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "x402 provider not configured", "detail": str(exc)},
        )
    except X402Error as exc:
        _log_warning(
            "x402_provider_error",
            task_id=task_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "x402 provider returned unexpected response", "detail": str(exc)},
        )
    except Exception as exc:
        _log_warning(
            "x402_reach_error",
            task_id=task_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to reach x402 provider", "detail": str(exc)},
        )

    provider_url = requirements.get("provider_url", "") if isinstance(requirements, dict) else ""
    amount_required = requirements.get("amount", str(_X402_AMOUNT)) if isinstance(requirements, dict) else str(_X402_AMOUNT)

    _log_event(
        "x402_payment_requirements_sent",
        task_id=task_id,
        provider_url=provider_url,
        amount_required=str(amount_required),
    )

    return {
        "payment_required": True,
        "requirements": requirements,
        "message": "Provide X-PAYMENT token to complete purchase",
    }


@router.post("/{task_id}/buy-data/confirm", summary="Complete x402 data purchase with payment token")
async def buy_data_confirm(
    task_id: str,
    body: ConfirmPurchaseRequest,
    db: Session = Depends(get_db),
):
    """
    Step 2 of the two-step x402 buy-data flow.

    Accepts a real X-PAYMENT token obtained by the frontend / agent via
    Kite Passport / MCP. Forwards it to the x402 provider; on success,
    advances task state to 'data_purchased' and persists a DataPurchase record.

    The backend NEVER generates or signs this token.

    Request body:
        { "payment_token": "<base64 X-PAYMENT string>" }
    """
    task = _get_task_or_404(task_id, db)
    if task.state != "funds_locked":
        raise HTTPException(
            status_code=409,
            detail={"error": "Task must be in 'funds_locked' state to confirm purchase", "current_state": task.state},
        )

    if not body.payment_token or not body.payment_token.strip():
        raise HTTPException(status_code=400, detail="payment_token is required and must not be empty")

    # Forward token to x402 provider — backend does NOT modify or sign the token
    try:
        client = X402Client()
        market_data = await client.complete_purchase(_X402_SYMBOL, body.payment_token.strip())
    except ConfigurationError as exc:
        _log_warning("x402_confirm_configuration_error", task_id=task_id, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={"error": "x402 provider not configured", "detail": str(exc)},
        )
    except X402PaymentRejected as exc:
        # Facilitator rejected the token — do NOT change task state
        _log_warning("x402_payment_rejected", task_id=task_id, error=str(exc))
        raise HTTPException(
            status_code=402,
            detail={"error": "Payment rejected by x402 facilitator", "detail": str(exc)},
        )
    except X402Error as exc:
        _log_warning("x402_confirm_provider_error", task_id=task_id, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail={"error": "x402 provider returned unexpected response", "detail": str(exc)},
        )
    except Exception as exc:
        _log_warning("x402_confirm_reach_error", task_id=task_id, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to reach x402 provider", "detail": str(exc)},
        )

    # External call succeeded — now advance task state and persist
    _safe_transition(task, "data_purchased")
    prev_state = task.state

    full_report = market_data.get("report") or market_data.get("summary", "")
    result_summary = (
        f"[x402 | {market_data.get('data_provider', 'KiteFuel Market Data')}] "
        f"{market_data.get('symbol', _X402_SYMBOL)} ({market_data.get('trend', 'unknown')})\n\n"
        f"{full_report}"
    )

    purchase = DataPurchase(
        task_id=task_id,
        provider="KiteFuel Market Data (x402)",
        amount=_X402_AMOUNT,
        result_summary=result_summary,
        payment_token=body.payment_token.strip(),
        purchased_at=_utcnow(),
    )
    db.add(purchase)
    task.state = "data_purchased"
    task.updated_at = _utcnow()
    _add_state_transition(
        db, task_id, prev_state, "data_purchased",
        note=f"x402 symbol={_X402_SYMBOL} network={market_data.get('settlement_network', 'kite-testnet')}",
    )
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("x402_confirm_db_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    token = body.payment_token.strip()
    payment_token_prefix = token[:20] if len(token) >= 20 else token

    _log_event(
        "x402_purchase_confirmed",
        task_id=task_id,
        state="data_purchased",
        symbol=market_data.get("symbol", _X402_SYMBOL),
        payment_token_prefix=f"{payment_token_prefix}...(first 20 chars)",
    )

    return _task_response(
        task,
        f"Research brief purchased via x402: {market_data.get('symbol', _X402_SYMBOL)} "
        f"({market_data.get('trend', 'unknown')}) — powered by Exa + Nansen + Claude",
    )


@router.post("/{task_id}/generate-report", summary="Generate the result report")
def generate_report(task_id: str, db: Session = Depends(get_db)):
    """
    Transition the task from 'data_purchased' to 'result_generated'.
    Updates the latest DataPurchase result_summary with a generated report note.
    """
    task = _get_task_or_404(task_id, db)
    _safe_transition(task, "result_generated")

    # Append report note to latest DataPurchase
    latest_purchase = (
        db.query(DataPurchase)
        .filter(DataPurchase.task_id == task_id)
        .order_by(DataPurchase.id.desc())
        .first()
    )
    if latest_purchase:
        latest_purchase.result_summary = (
            f"[REPORT GENERATED] {latest_purchase.result_summary}"
        )

    prev_state = task.state
    task.state = "result_generated"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "result_generated")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("generate_report_db_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    _log_event("report_generated", task_id=task_id, state="result_generated")
    return _task_response(task, "Report generated")


@router.post("/{task_id}/user-pay", summary="Register user revenue on-chain")
def user_pay(task_id: str, db: Session = Depends(get_db)):
    """
    Register demo revenue on the escrow contract.
    Calls registerRevenue on-chain FIRST; only updates DB on success.
    """
    task = _get_task_or_404(task_id, db)
    if task.state != "result_generated":
        raise HTTPException(
            status_code=409,
            detail={"error": "Task must be in 'result_generated' state for user payment", "current_state": task.state},
        )

    # 1. External side-effect first
    try:
        svc = ContractService()
        tx_hash = svc.register_revenue(
            task_id=_task_id_to_bytes32(task_id),
            value_wei=_REVENUE_WEI,
        )
    except ContractError as exc:
        _log_warning("user_pay_contract_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Contract call failed: {exc}")
    except Exception as exc:
        _log_warning("user_pay_unexpected_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Unexpected error during register_revenue: {exc}")

    # 2. Validate transition, then persist DB state
    _safe_transition(task, "user_paid")
    prev_state = task.state
    task.state = "user_paid"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "user_paid", note=f"revenue_wei={_REVENUE_WEI} tx={tx_hash}")
    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("user_pay_db_error", task_id=task_id, tx_hash=tx_hash, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    amount_kite = f"{_REVENUE_WEI / 10**18:.6f}".rstrip("0").rstrip(".")
    _log_event(
        "revenue_registered",
        task_id=task_id,
        state="user_paid",
        tx_hash=tx_hash,
        amount_kite=amount_kite,
        kite_explorer_url=_kite_tx_url(tx_hash),
    )
    return _task_response(task, f"Revenue registered (tx={tx_hash})")


@router.post("/{task_id}/settle", summary="Settle the escrow and close the task")
def settle(task_id: str, db: Session = Depends(get_db)):
    """
    Settle the escrow, repay the lender, release any borrower remainder, then close the task.
    Calls settle() on-chain FIRST; only updates DB on success.
    """
    task = _get_task_or_404(task_id, db)
    if task.state != "user_paid":
        raise HTTPException(
            status_code=409,
            detail={"error": "Task must be in 'user_paid' state to settle", "current_state": task.state},
        )

    # 1. External side-effect first
    try:
        svc = ContractService()
        tx_hash = svc.settle(task_id=_task_id_to_bytes32(task_id))
    except ContractError as exc:
        _log_warning("settle_contract_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Contract call failed: {exc}")
    except Exception as exc:
        _log_warning("settle_unexpected_error", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Unexpected error during settle: {exc}")

    # 2. Validate both state hops, then persist DB state
    _safe_transition(task, "lender_repaid")
    lender_paid = _REPAY_WEI / 10**18
    remainder = max(0.0, _REVENUE_WEI / 10**18 - lender_paid)

    repayment = RepaymentRecord(
        task_id=task_id,
        lender_paid=lender_paid,
        remainder_released=remainder,
        settled_at=_utcnow(),
    )
    db.add(repayment)

    prev_state = task.state
    task.state = "lender_repaid"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, prev_state, "lender_repaid", note=f"tx={tx_hash}")

    # Temporarily set state to validate lender_repaid -> task_closed
    task.state = "lender_repaid"
    _safe_transition(task, "task_closed")
    task.state = "task_closed"
    task.updated_at = _utcnow()
    _add_state_transition(db, task_id, "lender_repaid", "task_closed")

    try:
        db.commit()
        db.refresh(task)
    except Exception as exc:
        db.rollback()
        _log_warning("settle_db_error", task_id=task_id, tx_hash=tx_hash, error=str(exc))
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")

    _log_event(
        "task_settled",
        task_id=task_id,
        state="task_closed",
        tx_hash=tx_hash,
        kite_explorer_url=_kite_tx_url(tx_hash),
    )
    return _task_response(task, f"Task settled and closed (tx={tx_hash})")


@router.get("/{task_id}", summary="Get a task with full detail")
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Return a task along with all related entities and the next recommended action."""
    task = _get_task_or_404(task_id, db)
    return _task_detail_response(task)


@router.get("", summary="List all tasks")
def list_tasks(db: Session = Depends(get_db)):
    """Return all tasks ordered newest first, each with a next_action label."""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return {
        "tasks": [
            {
                "id": t.id,
                "state": t.state,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "next_action": next_action(t.state),
            }
            for t in tasks
        ],
        "count": len(tasks),
    }


@router.delete("/all", summary="Delete all demo tasks")
def delete_all_tasks(db: Session = Depends(get_db)):
    """
    Delete all tasks and their related data.
    Safe because Task uses cascade='all, delete-orphan' on all child relationships.
    """
    try:
        tasks = db.query(Task).all()
        for t in tasks:
            db.delete(t)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {exc}")
    return {"message": "All demo tasks deleted", "deleted": len(tasks)}
