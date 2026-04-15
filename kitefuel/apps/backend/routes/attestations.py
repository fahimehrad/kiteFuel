"""
GET /tasks/{task_id}/attestations

Returns on-chain receipts for every tx_hash recorded against a task.
Each attestation is verifiable directly on Kite Chain testnet via KiteScan.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from web3 import Web3

from database import get_db
from models import EscrowPosition, StateTransition, Task

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["attestations"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPLORER_BASE = "https://testnet.kitescan.ai/tx"

# Events that carry a value amount (in wei)
_AMOUNT_EVENTS = {
    "EscrowCreated",     # creditAmount
    "CreditFunded",      # amount
    "SpendRecorded",     # amount
    "RevenueRegistered", # amount
    "LenderRepaid",      # amount
    "RemainderReleased", # amount
}

# ---------------------------------------------------------------------------
# ABI loading (reuses the Foundry artifact)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ABI_PATH = (
    _REPO_ROOT / "apps" / "contracts" / "out"
    / "KiteFuelEscrow.sol" / "KiteFuelEscrow.json"
)


def _load_abi() -> list[dict]:
    if not _ABI_PATH.exists():
        raise FileNotFoundError(
            f"Contract ABI not found at {_ABI_PATH}. Run `forge build` first."
        )
    with _ABI_PATH.open() as fh:
        return json.load(fh)["abi"]


# ---------------------------------------------------------------------------
# RPC helper (mirrors contract_service.get_rpc_url)
# ---------------------------------------------------------------------------

def _get_rpc_url() -> str:
    return os.environ.get("KITE_RPC_URL") or os.environ.get("ANVIL_RPC_URL", "http://localhost:8545")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class AttestationItem(BaseModel):
    event: str
    tx_hash: str
    block_number: int | None
    timestamp: str | None          # ISO-8601 or null
    amount_kite: str | None        # human-readable KITE, e.g. "0.01"
    explorer_url: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{task_id}/attestations", response_model=list[AttestationItem])
def get_attestations(task_id: str, db: Session = Depends(get_db)) -> list[AttestationItem]:
    """Return verifiable on-chain attestations for every action taken on this task."""

    # Confirm task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # ── Collect tx hashes from EscrowPosition ────────────────────────────────
    escrow_rows: list[EscrowPosition] = (
        db.query(EscrowPosition).filter(EscrowPosition.task_id == task_id).all()
    )

    # ── Collect tx hashes embedded in StateTransition.note (e.g. "tx=0x...") ─
    transition_rows: list[StateTransition] = (
        db.query(StateTransition).filter(StateTransition.task_id == task_id).all()
    )
    _TX_RE = re.compile(r"tx=(0x[0-9a-fA-F]{64})")

    # Build deduplicated list preserving insertion order
    seen: set[str] = set()
    tx_hashes: list[str] = []

    for h in [row.tx_hash for row in escrow_rows if row.tx_hash]:
        if h not in seen:
            seen.add(h)
            tx_hashes.append(h)

    for row in transition_rows:
        if row.note:
            for match in _TX_RE.findall(row.note):
                if match not in seen:
                    seen.add(match)
                    tx_hashes.append(match)

    if not tx_hashes:
        return []

    # Lazily connect to the chain
    try:
        abi = _load_abi()
        w3 = Web3(Web3.HTTPProvider(_get_rpc_url()))
        contract_address = os.environ.get("CONTRACT_ADDRESS")
        contract = (
            w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
            if contract_address
            else None
        )
    except Exception as exc:
        logger.warning("attestations_init_failed", error=str(exc))
        # Return minimal attestation stubs so the frontend doesn't crash
        return [
            AttestationItem(
                event="unknown",
                tx_hash=h,
                block_number=None,
                timestamp=None,
                amount_kite=None,
                explorer_url=f"{EXPLORER_BASE}/{h}",
            )
            for h in tx_hashes
        ]

    results: list[AttestationItem] = []

    for tx_hash in tx_hashes:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
        except Exception as exc:
            logger.warning("receipt_fetch_failed", tx_hash=tx_hash, error=str(exc))
            results.append(
                AttestationItem(
                    event="unknown",
                    tx_hash=tx_hash,
                    block_number=None,
                    timestamp=None,
                    amount_kite=None,
                    explorer_url=f"{EXPLORER_BASE}/{tx_hash}",
                )
            )
            continue

        if receipt is None:
            # Pending / not found
            results.append(
                AttestationItem(
                    event="unknown",
                    tx_hash=tx_hash,
                    block_number=None,
                    timestamp=None,
                    amount_kite=None,
                    explorer_url=f"{EXPLORER_BASE}/{tx_hash}",
                )
            )
            continue

        block_number: int = receipt["blockNumber"]
        iso_ts: str | None = None

        try:
            block = w3.eth.get_block(block_number)
            ts: int = block["timestamp"]  # type: ignore[index]
            iso_ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            pass  # timestamp is best-effort

        # Decode logs
        decoded_events = _decode_logs(contract, receipt) if contract else []

        if decoded_events:
            for evt_name, amount_wei in decoded_events:
                amount_kite: str | None = None
                if amount_wei is not None:
                    # Convert wei → KITE (18 decimals), trim trailing zeros
                    kite_val = amount_wei / 10**18
                    amount_kite = f"{kite_val:.6f}".rstrip("0").rstrip(".")

                results.append(
                    AttestationItem(
                        event=evt_name,
                        tx_hash=tx_hash,
                        block_number=block_number,
                        timestamp=iso_ts,
                        amount_kite=amount_kite,
                        explorer_url=f"{EXPLORER_BASE}/{tx_hash}",
                    )
                )
        else:
            # Receipt found but no recognised events — still surface the tx
            results.append(
                AttestationItem(
                    event="confirmed",
                    tx_hash=tx_hash,
                    block_number=block_number,
                    timestamp=iso_ts,
                    amount_kite=None,
                    explorer_url=f"{EXPLORER_BASE}/{tx_hash}",
                )
            )

    return results


# ---------------------------------------------------------------------------
# Log decoding helper
# ---------------------------------------------------------------------------

def _decode_logs(contract: Any, receipt: Any) -> list[tuple[str, int | None]]:
    """Return list of (event_name, optional_amount_wei) tuples for known events."""
    results: list[tuple[str, int | None]] = []

    # Map of event name → argument name that holds the KITE value
    _AMOUNT_ARG: dict[str, str] = {
        "EscrowCreated":     "creditAmount",
        "CreditFunded":      "amount",
        "SpendRecorded":     "amount",
        "RevenueRegistered": "amount",
        "LenderRepaid":      "amount",
        "RemainderReleased": "amount",
    }

    known_events = {
        "EscrowCreated", "CreditFunded", "SpendRecorded",
        "RevenueRegistered", "LenderRepaid", "RemainderReleased",
    }

    for event_name in known_events:
        try:
            event_obj = getattr(contract.events, event_name)
            logs = event_obj().process_receipt(receipt, errors="discard")  # type: ignore[call-arg]
            for log in logs:
                amount_arg = _AMOUNT_ARG.get(event_name)
                amount_wei: int | None = None
                if amount_arg:
                    raw = log.get("args", {}).get(amount_arg)
                    if isinstance(raw, int):
                        amount_wei = raw
                results.append((event_name, amount_wei))
        except Exception:
            # Silently skip events that fail to decode
            pass

    return results
