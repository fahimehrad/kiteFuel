from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    state = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    credit_offers = relationship("CreditOffer", back_populates="task", cascade="all, delete-orphan")
    escrow_positions = relationship("EscrowPosition", back_populates="task", cascade="all, delete-orphan")
    data_purchases = relationship("DataPurchase", back_populates="task", cascade="all, delete-orphan")
    repayment_records = relationship("RepaymentRecord", back_populates="task", cascade="all, delete-orphan")
    state_transitions = relationship("StateTransition", back_populates="task", cascade="all, delete-orphan")


class CreditOffer(Base):
    __tablename__ = "credit_offers"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    lender_address = Column(String, nullable=False)
    credit_amount = Column(Float, nullable=False)
    repay_amount = Column(Float, nullable=False)

    task = relationship("Task", back_populates="credit_offers")


class EscrowPosition(Base):
    __tablename__ = "escrow_positions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    contract_address = Column(String, nullable=False)
    tx_hash = Column(String, nullable=False)
    state = Column(String, nullable=False)

    task = relationship("Task", back_populates="escrow_positions")


class DataPurchase(Base):
    __tablename__ = "data_purchases"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    result_summary = Column(Text, nullable=True)
    payment_token = Column(Text, nullable=True)
    purchased_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    task = relationship("Task", back_populates="data_purchases")


class RepaymentRecord(Base):
    __tablename__ = "repayment_records"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    lender_paid = Column(Float, nullable=False)
    remainder_released = Column(Float, nullable=False)
    settled_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    task = relationship("Task", back_populates="repayment_records")


class StateTransition(Base):
    __tablename__ = "state_transitions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    from_state = Column(String, nullable=False)
    to_state = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    note = Column(String, nullable=True)

    task = relationship("Task", back_populates="state_transitions")
