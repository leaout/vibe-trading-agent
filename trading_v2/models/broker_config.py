# coding: utf-8
"""Encrypted local configuration for the Eastmoney broker account."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.models.crypto import encrypt_secret
from trading_v2.storage.database import Base, Database

BROKER_CONFIG_ID = "eastmoney-default"


class BrokerConfigRecord(Base):
    __tablename__ = "broker_config_v2"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_no_encrypted: Mapped[str] = mapped_column(String(2000), default="")
    account_last4: Mapped[str] = mapped_column(String(4), default="")
    password_encrypted: Mapped[str] = mapped_column(String(4096), default="")
    session_file: Mapped[str] = mapped_column(String(500), default="data/eastmoney_trader.session")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def account_hint(self) -> str:
        return f"••••{self.account_last4}" if self.account_last4 else ""


class BrokerConfigRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self) -> BrokerConfigRecord | None:
        with self.database.sessions() as db:
            return db.get(BrokerConfigRecord, BROKER_CONFIG_ID)

    def save(self, values: dict[str, str | bool]) -> BrokerConfigRecord:
        now = datetime.now(timezone.utc)
        account_no = str(values.get("account_no", "")).strip()
        password = str(values.get("password", ""))
        with self.database.sessions.begin() as db:
            record = db.get(BrokerConfigRecord, BROKER_CONFIG_ID)
            if record is None:
                record = BrokerConfigRecord(
                    id=BROKER_CONFIG_ID,
                    account_no_encrypted="",
                    account_last4="",
                    password_encrypted="",
                    session_file="data/eastmoney_trader.session",
                    updated_at=now,
                )
                db.add(record)
            if account_no:
                record.account_no_encrypted = encrypt_secret(account_no)
                record.account_last4 = account_no[-4:]
            if password:
                record.password_encrypted = encrypt_secret(password)
            if "session_file" in values:
                record.session_file = str(values["session_file"]).strip()
            record.updated_at = now
        result = self.get()
        if result is None:
            raise RuntimeError("保存券商配置后未能重新读取")
        return result
