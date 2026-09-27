# coding: utf-8
"""Persistent, write-only-secret model configuration profiles."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, String, select
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.storage.database import Base, Database
from trading_v2.models.crypto import decrypt_secret, encrypt_secret


class ModelProfileRecord(Base):
    __tablename__ = "model_profiles_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_key_env: Mapped[str] = mapped_column(String(120))
    secret_value: Mapped[str] = mapped_column(String(2000), default="")
    timeout_seconds: Mapped[float] = mapped_column(Float, default=20.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelProfileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_profiles(self) -> list[ModelProfileRecord]:
        with self.database.sessions() as db:
            return list(db.scalars(select(ModelProfileRecord).order_by(ModelProfileRecord.created_at)))

    def get(self, profile_id: str) -> ModelProfileRecord | None:
        with self.database.sessions() as db:
            return db.get(ModelProfileRecord, profile_id)

    def save(self, profile_id: str | None, values: dict) -> ModelProfileRecord:
        now = datetime.now(timezone.utc)
        values = dict(values)
        if values.get("secret_value"):
            values["secret_value"] = encrypt_secret(values["secret_value"])
        with self.database.sessions.begin() as db:
            record = db.get(ModelProfileRecord, profile_id) if profile_id else None
            if record is None:
                record = ModelProfileRecord(
                    id=profile_id or str(uuid4()), created_at=now, secret_value="",
                )
                db.add(record)
            for key, value in values.items():
                if key != "secret_value" or value:
                    setattr(record, key, value)
            if record.enabled:
                for other in db.scalars(select(ModelProfileRecord).where(ModelProfileRecord.id != record.id)):
                    other.enabled = False
            record.updated_at = now
        return self.get(record.id)  # type: ignore[return-value]

    def delete(self, profile_id: str) -> bool:
        with self.database.sessions.begin() as db:
            record = db.get(ModelProfileRecord, profile_id)
            if record is None:
                return False
            db.delete(record)
            return True
