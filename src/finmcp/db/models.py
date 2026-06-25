from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # provider_account_id
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    iban: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account"
    )


class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    available: Mapped[float | None] = mapped_column(Float, nullable=True)
    current: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # provider tx id
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String)
    booked_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String)  # debit | credit
    merchant_name: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_category: Mapped[str | None] = mapped_column(String, nullable=True)
    my_category: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped["Account"] = relationship(back_populates="transactions")


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String)  # subcadena, case-insensitive
    category: Mapped[str] = mapped_column(String)
    field: Mapped[str] = mapped_column(String, default="any")  # merchant|description|any
    priority: Mapped[int] = mapped_column(Integer, default=100)  # menor = antes


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")
    accounts_synced: Mapped[int] = mapped_column(Integer, default=0)
    tx_added: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
