# coding: utf-8
"""Application service for system paper accounts and rule-only execution."""

import asyncio
from decimal import Decimal

from trading_v2.agent.models import StrategySpec
from trading_v2.domain.enums import SignalSide, TradingMode
from trading_v2.domain.signal import Signal
from trading_v2.events import InMemoryEventStream
from trading_v2.paper.models import PaperAccount, PaperAccountDetail, PaperOrder
from trading_v2.paper.repository import PaperRepository
from trading_v2.sessions.service import TradingSessionService


class PaperTradingService:
    def __init__(
        self,
        repository: PaperRepository,
        sessions: TradingSessionService,
        events: InMemoryEventStream,
    ) -> None:
        self.repository = repository
        self.sessions = sessions
        self.events = events

    async def initialize(self) -> PaperAccount:
        await asyncio.to_thread(self.repository.database.create_schema)
        return await asyncio.to_thread(self.repository.ensure_default)

    async def create_account(self, name: str, cash: Decimal, currency: str) -> PaperAccount:
        account = await asyncio.to_thread(
            self.repository.create_account, name, cash, currency
        )
        await self.events.publish("paper.account.created", {"account_id": account.id})
        return account

    async def list_accounts(self) -> list[PaperAccount]:
        return await asyncio.to_thread(self.repository.list_accounts)

    async def detail(self, account_id: str) -> PaperAccountDetail | None:
        return await asyncio.to_thread(self.repository.detail, account_id)

    async def account_for_session(self, session_id: str) -> PaperAccountDetail | None:
        account = await asyncio.to_thread(self.repository.account_for_session, session_id)
        return await self.detail(account.id) if account else None

    async def enable(self, session_id: str, account_id: str | None = None) -> PaperAccount | None:
        session = await self.sessions.get_session(session_id)
        if session is None:
            return None
        account = (
            await asyncio.to_thread(self.repository.get_account, account_id)
            if account_id else await asyncio.to_thread(self.repository.ensure_default)
        )
        if account is None:
            raise ValueError("paper account not found")
        await asyncio.to_thread(self.repository.bind, session_id, account.id)
        await self.sessions.set_mode(session_id, TradingMode.PAPER)
        await self.events.publish("paper.enabled", {
            "session_id": session_id, "account_id": account.id,
        })
        return account

    async def process_signal(
        self, session_id: str, strategy: StrategySpec, signal: Signal,
    ) -> PaperOrder | None:
        session = await self.sessions.get_session(session_id)
        if session is None or session.mode != TradingMode.PAPER:
            return None
        account = await asyncio.to_thread(self.repository.account_for_session, session_id)
        if account is None:
            return None
        side = "buy" if signal.side == SignalSide.BUY else "sell"
        order = await asyncio.to_thread(
            self.repository.execute,
            account.id, session_id, str(signal.id), signal.instrument.canonical,
            side, Decimal(str(signal.indicators["close"])),
            strategy.risk.max_position_pct,
        )
        await self.events.publish(
            "order.filled" if order.status == "filled" else "risk.rejected",
            {
                "session_id": session_id, "account_id": account.id,
                "signal_id": str(signal.id), "order_id": order.id,
                "side": order.side, "quantity": str(order.quantity),
                "price": str(order.price), "fee": str(order.fee),
                "reason": order.rejection_reason,
            },
        )
        return order
