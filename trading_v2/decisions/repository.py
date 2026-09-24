# coding: utf-8
"""Persistence for one idempotent model decision per candidate signal."""

import json
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


class DecisionAuditRecord(Base):
    """Immutable decision inputs and append-once model/execution outcomes."""

    __tablename__ = "decision_audits_v2"

    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_signals_v2.id", ondelete="CASCADE"), primary_key=True
    )
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    context_json: Mapped[str] = mapped_column(Text)
    model_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DecisionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_for_signal(self, signal_id: str) -> ModelDecision | None:
        with self.database.sessions() as db:
            row = db.scalar(select(DecisionRecord).where(DecisionRecord.signal_id == signal_id))
            return self._model(row) if row else None

    def save_context(self, signal_id: str, session_id: str, context: dict) -> None:
        with self.database.sessions.begin() as db:
            row = db.get(DecisionAuditRecord, signal_id)
            if row is None:
                db.add(DecisionAuditRecord(
                    signal_id=signal_id,
                    session_id=session_id,
                    context_json=json.dumps(context, ensure_ascii=False, default=str),
                    started_at=datetime.now(timezone.utc),
                ))

    def save_model_result(self, signal_id: str, result: dict) -> None:
        with self.database.sessions.begin() as db:
            row = db.get(DecisionAuditRecord, signal_id)
            if row is None:
                return
            completed_at = datetime.now(timezone.utc)
            row.model_response_json = json.dumps(result, ensure_ascii=False, default=str)
            row.completed_at = completed_at
            row.duration_ms = max(0, int((completed_at - row.started_at).total_seconds() * 1000))

    def save_execution(self, signal_id: str, outcome: dict) -> None:
        with self.database.sessions.begin() as db:
            row = db.get(DecisionAuditRecord, signal_id)
            if row is not None:
                row.execution_json = json.dumps(outcome, ensure_ascii=False, default=str)
                if row.completed_at is None:
                    row.completed_at = datetime.now(timezone.utc)
                    row.duration_ms = max(0, int((row.completed_at - row.started_at).total_seconds() * 1000))

    def get_audit(self, session_id: str, signal_id: str) -> dict | None:
        with self.database.sessions() as db:
            row = db.scalar(select(DecisionAuditRecord).where(
                DecisionAuditRecord.session_id == session_id,
                DecisionAuditRecord.signal_id == signal_id,
            ))
            decision = db.scalar(select(DecisionRecord).where(
                DecisionRecord.session_id == session_id,
                DecisionRecord.signal_id == signal_id,
            ))
        if row is None:
            return None
        return {
            "signal_id": row.signal_id,
            "session_id": row.session_id,
            "context": json.loads(row.context_json),
            "model_response": json.loads(row.model_response_json) if row.model_response_json else None,
            "decision": self._model(decision).model_dump(mode="json") if decision else None,
            "execution": json.loads(row.execution_json) if row.execution_json else None,
            "started_at": row.started_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "duration_ms": row.duration_ms,
        }

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
