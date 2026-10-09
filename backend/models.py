from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt: Mapped[str] = mapped_column(Text)
    budget_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="complete")
    total_spent: Mapped[float] = mapped_column(Float, default=0)
    reserved: Mapped[float] = mapped_column(Float, default=0)
    report: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(128), default="")
    amount_usd: Mapped[float] = mapped_column(Float, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    transaction_ref: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
