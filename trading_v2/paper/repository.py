# coding: utf-8
"""Transactional storage for system-owned paper accounts."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.paper.models import PaperAccount, PaperAccountDetail, PaperFill, PaperOrder, PaperPosition
from trading_v2.storage.database import Base, Database

MONEY = Numeric(20, 6)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class PaperAccountRecord(Base):
    __tablename__ = "paper_accounts_v2"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(10))
    initial_cash: Mapped[Decimal] = mapped_column(MONEY)
    cash: Mapped[Decimal] = mapped_column(MONEY)
    frozen_cash: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperSessionBindingRecord(Base):
    __tablename__ = "paper_session_bindings_v2"
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_sessions_v2.id", ondelete="CASCADE"), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_accounts_v2.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperPositionRecord(Base):
    __tablename__ = "paper_positions_v2"
    __table_args__ = (UniqueConstraint("account_id", "instrument", name="uq_paper_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    instrument: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[Decimal] = mapped_column(MONEY)
    available_quantity: Mapped[Decimal] = mapped_column(MONEY)
    average_cost: Mapped[Decimal] = mapped_column(MONEY)
    last_price: Mapped[Decimal] = mapped_column(MONEY)
    trading_day: Mapped[date] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperOrderRecord(Base):
    __tablename__ = "paper_orders_v2"
    __table_args__ = (UniqueConstraint("signal_id", name="uq_paper_order_signal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    signal_id: Mapped[str] = mapped_column(String(36))
    instrument: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(MONEY)
    price: Mapped[Decimal] = mapped_column(MONEY)
    fee: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(20))
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PaperFillRecord(Base):
    __tablename__ = "paper_fills_v2"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), index=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    instrument: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(MONEY)
    price: Mapped[Decimal] = mapped_column(MONEY)
    fee: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PaperLedgerRecord(Base):
    __tablename__ = "paper_ledger_v2"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    balance_after: Mapped[Decimal] = mapped_column(MONEY)
    description: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PaperRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_account(self, name: str, cash: Decimal, currency: str) -> PaperAccount:
        now, account_id = _now(), str(uuid4())
        with self.database.sessions.begin() as db:
            db.add(PaperAccountRecord(id=account_id, name=name.strip(), currency=currency.upper(), initial_cash=cash, cash=cash, frozen_cash=Decimal("0"), realized_pnl=Decimal("0"), created_at=now, updated_at=now))
            db.add(PaperLedgerRecord(id=str(uuid4()), account_id=account_id, entry_type="initial_deposit", amount=cash, balance_after=cash, description="模拟账户初始资金", created_at=now))
        return self.get_account(account_id)

    def ensure_default(self) -> PaperAccount:
        accounts = self.list_accounts()
        return accounts[0] if accounts else self.create_account("系统模拟账户", Decimal("1000000"), "CNY")

    def list_accounts(self) -> list[PaperAccount]:
        with self.database.sessions() as db:
            return [self._account(db, row) for row in db.scalars(select(PaperAccountRecord).order_by(PaperAccountRecord.created_at)).all()]

    def get_account(self, account_id: str) -> PaperAccount | None:
        with self.database.sessions() as db:
            row = db.get(PaperAccountRecord, account_id)
            return self._account(db, row) if row else None

    def detail(self, account_id: str) -> PaperAccountDetail | None:
        with self.database.sessions() as db:
            account = db.get(PaperAccountRecord, account_id)
            if account is None:
                return None
            positions = db.scalars(select(PaperPositionRecord).where(PaperPositionRecord.account_id == account_id, PaperPositionRecord.quantity > 0)).all()
            orders = db.scalars(select(PaperOrderRecord).where(PaperOrderRecord.account_id == account_id).order_by(PaperOrderRecord.created_at.desc()).limit(100)).all()
            fills = db.scalars(select(PaperFillRecord).where(PaperFillRecord.account_id == account_id).order_by(PaperFillRecord.created_at.desc()).limit(100)).all()
            return PaperAccountDetail(account=self._account(db, account), positions=[self._position(x) for x in positions], orders=[self._order(x) for x in orders], fills=[self._fill(x) for x in fills])

    def bind(self, session_id: str, account_id: str) -> None:
        with self.database.sessions.begin() as db:
            row = db.get(PaperSessionBindingRecord, session_id)
            if row:
                row.account_id = account_id
            else:
                db.add(PaperSessionBindingRecord(session_id=session_id, account_id=account_id, created_at=_now()))

    def account_for_session(self, session_id: str) -> PaperAccount | None:
        with self.database.sessions() as db:
            binding = db.get(PaperSessionBindingRecord, session_id)
            if not binding:
                return None
            row = db.get(PaperAccountRecord, binding.account_id)
            return self._account(db, row) if row else None

    def mark_price(self, instrument: str, price: Decimal) -> int:
        """Mark every open paper position in an instrument to the latest closed bar."""
        now = _now()
        with self.database.sessions.begin() as db:
            positions = db.scalars(
                select(PaperPositionRecord).where(
                    PaperPositionRecord.instrument == instrument,
                    PaperPositionRecord.quantity > 0,
                )
            ).all()
            account_ids = {position.account_id for position in positions}
            for position in positions:
                position.last_price = price
                position.updated_at = now
            for account_id in account_ids:
                account = db.get(PaperAccountRecord, account_id)
                if account is not None:
                    account.updated_at = now
            return len(positions)

    def execute(self, account_id: str, session_id: str, signal_id: str, instrument: str, side: str, price: Decimal, allocation: Decimal) -> PaperOrder:
        now = _now()
        with self.database.sessions.begin() as db:
            duplicate = db.scalar(select(PaperOrderRecord).where(PaperOrderRecord.signal_id == signal_id))
            if duplicate:
                return self._order(duplicate)
            account = db.get(PaperAccountRecord, account_id)
            if not account:
                raise ValueError("模拟账户不存在")
            position = db.scalar(select(PaperPositionRecord).where(PaperPositionRecord.account_id == account_id, PaperPositionRecord.instrument == instrument))
            if position and position.trading_day < now.date():
                position.available_quantity = position.quantity
                position.trading_day = now.date()
            lot = Decimal("100") if instrument.startswith("cn_equity:") else Decimal("0.000001")
            if side == "buy":
                current_value = position.quantity * price if position else Decimal("0")
                remaining_allocation = max(
                    Decimal("0"), account.initial_cash * allocation - current_value,
                )
                budget = min(account.cash, remaining_allocation)
                quantity = (budget / price // lot) * lot
                gross = quantity * price
                fee = max(Decimal("5"), gross * Decimal("0.0003")) if quantity else Decimal("0")
                rejection = None if quantity > 0 and gross + fee <= account.cash else "可用资金不足以满足最小交易单位"
            else:
                quantity = position.available_quantity if position else Decimal("0")
                gross = quantity * price
                fee = max(Decimal("5"), gross * Decimal("0.0003")) + gross * Decimal("0.0005") if quantity else Decimal("0")
                rejection = None if quantity > 0 else "无可卖持仓（A股当日买入不可卖）"
            order = PaperOrderRecord(id=str(uuid4()), account_id=account_id, session_id=session_id, signal_id=signal_id, instrument=instrument, side=side, quantity=quantity, price=price, fee=fee, status="rejected" if rejection else "filled", rejection_reason=rejection, created_at=now)
            db.add(order)
            if rejection:
                db.flush()
                return self._order(order)
            if side == "buy":
                cash_delta = -(gross + fee)
                account.cash += cash_delta
                if position:
                    old_cost = position.average_cost * position.quantity
                    position.quantity += quantity
                    position.average_cost = (old_cost + gross + fee) / position.quantity
                    position.last_price, position.updated_at = price, now
                    if not instrument.startswith("cn_equity:"):
                        position.available_quantity += quantity
                else:
                    available = Decimal("0") if instrument.startswith("cn_equity:") else quantity
                    db.add(PaperPositionRecord(id=str(uuid4()), account_id=account_id, instrument=instrument, quantity=quantity, available_quantity=available, average_cost=(gross + fee) / quantity, last_price=price, trading_day=now.date(), updated_at=now))
            else:
                cash_delta = gross - fee
                account.cash += cash_delta
                account.realized_pnl += (price - position.average_cost) * quantity - fee
                position.quantity -= quantity
                position.available_quantity -= quantity
                position.last_price, position.updated_at = price, now
            account.updated_at = now
            db.add(PaperFillRecord(id=str(uuid4()), order_id=order.id, account_id=account_id, instrument=instrument, side=side, quantity=quantity, price=price, fee=fee, created_at=now))
            db.add(PaperLedgerRecord(id=str(uuid4()), account_id=account_id, order_id=order.id, entry_type=f"paper_{side}", amount=cash_delta, balance_after=account.cash, description=f"{side.upper()} {instrument} {quantity} @ {price}", created_at=now))
            db.flush()
            return self._order(order)

    @staticmethod
    def _account(db, row: PaperAccountRecord) -> PaperAccount:
        positions = db.scalars(select(PaperPositionRecord).where(PaperPositionRecord.account_id == row.id, PaperPositionRecord.quantity > 0)).all()
        market_value = sum((p.quantity * p.last_price for p in positions), Decimal("0"))
        unrealized = sum(((p.last_price - p.average_cost) * p.quantity for p in positions), Decimal("0"))
        return PaperAccount(id=row.id, name=row.name, currency=row.currency, initial_cash=row.initial_cash, cash=row.cash, frozen_cash=row.frozen_cash, market_value=market_value, total_equity=row.cash + market_value, realized_pnl=row.realized_pnl, unrealized_pnl=unrealized, created_at=_aware(row.created_at), updated_at=_aware(row.updated_at))

    @staticmethod
    def _position(row: PaperPositionRecord) -> PaperPosition:
        return PaperPosition(account_id=row.account_id, instrument=row.instrument, quantity=row.quantity, available_quantity=row.available_quantity, average_cost=row.average_cost, last_price=row.last_price, market_value=row.quantity * row.last_price, unrealized_pnl=(row.last_price - row.average_cost) * row.quantity, updated_at=_aware(row.updated_at))

    @staticmethod
    def _order(row: PaperOrderRecord) -> PaperOrder:
        return PaperOrder(id=row.id, account_id=row.account_id, session_id=row.session_id, signal_id=row.signal_id, instrument=row.instrument, side=row.side, quantity=row.quantity, price=row.price, fee=row.fee, status=row.status, rejection_reason=row.rejection_reason, created_at=_aware(row.created_at))

    @staticmethod
    def _fill(row: PaperFillRecord) -> PaperFill:
        return PaperFill(id=row.id, order_id=row.order_id, account_id=row.account_id, instrument=row.instrument, side=row.side, quantity=row.quantity, price=row.price, fee=row.fee, created_at=_aware(row.created_at))
