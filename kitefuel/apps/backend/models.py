from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum
from sqlalchemy.sql import func
from database import Base
import enum


class LoanStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    repaid = "repaid"
    defaulted = "defaulted"


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    agent_address = Column(String, nullable=False, index=True)
    amount_wei = Column(Numeric, nullable=False)
    status = Column(Enum(LoanStatus), default=LoanStatus.pending, nullable=False)
    tx_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
