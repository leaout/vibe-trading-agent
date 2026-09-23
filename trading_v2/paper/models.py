# coding: utf-8
"""API models for the system-owned simulated trading account."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperAccount(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    currency: str
    initial_cash: Decimal
    cash: Decimal
    frozen_cash: Decimal
    market_value: Decimal
    total_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    created_at: datetime
    updated_at: datetime


class PaperPosition(BaseModel):
    model_config = ConfigDict(frozen=True)
    account_id: str
    instrument: str
    quantity: Decimal
    available_quantity: Decimal
    average_cost: Decimal
    last_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    updated_at: datetime


class PaperOrder(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    account_id: str
    session_id: str
    signal_id: str
    instrument: str
    side: Literal["buy", "sell"]
    order_type: Literal["market"] = "market"
    quantity: Decimal
    price: Decimal
    fee: Decimal
    status: Literal["filled", "rejected"]
    rejection_reason: str | None = None
    created_at: datetime


class PaperFill(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    order_id: str
    account_id: str
    instrument: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal
    fee: Decimal
    created_at: datetime


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    account_id: str
    order_id: str | None = None
    entry_type: str
    amount: Decimal
    balance_after: Decimal
    description: str
    created_at: datetime


class PaperAccountDetail(BaseModel):
    account: PaperAccount
    positions: list[PaperPosition] = Field(default_factory=list)
    orders: list[PaperOrder] = Field(default_factory=list)
    fills: list[PaperFill] = Field(default_factory=list)


class CreatePaperAccount(BaseModel):
    name: str = Field(default="系统模拟账户", min_length=1, max_length=80)
    initial_cash: Decimal = Field(default=Decimal("1000000"), gt=0)
    currency: str = Field(default="CNY", min_length=3, max_length=10)


class EnablePaperTrading(BaseModel):
    account_id: str | None = None
