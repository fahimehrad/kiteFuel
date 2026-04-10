from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TaskState(str, Enum):
    task_created = "task_created"
    credit_requested = "credit_requested"
    credit_approved = "credit_approved"
    funds_locked = "funds_locked"
    data_purchased = "data_purchased"
    result_generated = "result_generated"
    user_paid = "user_paid"
    lender_repaid = "lender_repaid"
    task_closed = "task_closed"
    task_failed = "task_failed"


class Task(BaseModel):
    id: str
    state: TaskState
    created_at: str
    next_action: Optional[str] = None


class CreditOffer(BaseModel):
    task_id: str
    lender_address: str
    credit_amount: float
    repay_amount: float


class EscrowPosition(BaseModel):
    task_id: str
    contract_address: str
    tx_hash: str
    state: str


class DataPurchase(BaseModel):
    task_id: str
    provider: str
    amount: float
    result_summary: str


class RepaymentRecord(BaseModel):
    task_id: str
    lender_paid: float
    remainder_released: float
    settled_at: str
