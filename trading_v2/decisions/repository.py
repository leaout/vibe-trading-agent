# coding: utf-8
"""Persistence for one idempotent model decision per candidate signal."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.decisions.models import ModelDecision
from trading_v2.domain.enums import DecisionAction
from trading_v2.storage.database import Base, Database


class DecisionRecord(Base):
    __tablename__ = "model_decisions_v2"
    __table_args__ = (UniqueConstraint("signal_id", name="uq_model_decision_signal"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_signals_v2.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_sessions_v2.id", ondelete="CASCADE"), index=True)
    strategy_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    model_provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DecisionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_for_signal(self, signal_id: str) -> ModelDecision | None:
        with self.database.sessions() as db:
            row = db.scalar(select(DecisionRecord).where(DecisionRecord.signal_id == signal_id))
            return self._model(row) if row else None

    def save(self, *, signal_id: str, session_id: str, strategy_version: int,
             action: DecisionAction, confidence: float, rationale: str,
             model_provider: str, model_name: str, status: str,
             error: str | None = None) -> ModelDecision:
        existing = self.get_for_signal(signal_id)
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc)
        row = DecisionRecord(
            id=str(uuid4()), signal_id=signal_id, session_id=session_id,
            strategy_version=strategy_version, action=action.value,
            confidence=confidence, rationale=rationale,
            model_provider=model_provider, model_name=model_name,
            prompt_version="decision-v1", status=status, error=error,
            created_at=now,
        )
        try:
            with self.database.sessions.begin() as db:
                db.add(row)
        except IntegrityError:
            existing = self.get_for_signal(signal_id)
            if existing is None:
                raise
            return existing
        return self._model(row)

    def list_for_session(self, session_id: str, limit: int = 200) -> list[ModelDecision]:
        with self.database.sessions() as db:
            rows = db.scalars(
                select(DecisionRecord).where(DecisionRecord.session_id == session_id)
                .order_by(DecisionRecord.created_at.desc()).limit(limit)
            ).all()
        return [self._model(row) for row in reversed(rows)]

    @staticmethod
    def event_projection(decision: ModelDecision) -> dict:
        return {
            "id": decision.id, "timestamp": decision.created_at.isoformat(),
            "type": "model", "title": f"AI 决策：{decision.action.value.upper()}",
            "detail": f"置信度 {decision.confidence:.0%} · {decision.rationale}",
            "state": "warning" if decision.action == DecisionAction.HOLD else "success",
        }

    @staticmethod
    def _model(row: DecisionRecord) -> ModelDecision:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return ModelDecision(
            id=row.id, signal_id=row.signal_id, session_id=row.session_id,
            strategy_version=row.strategy_version, action=DecisionAction(row.action),
            confidence=row.confidence, rationale=row.rationale,
            model_provider=row.model_provider, model_name=row.model_name,
            prompt_version=row.prompt_version, status=row.status,
            error=row.error, created_at=created_at,
        )
