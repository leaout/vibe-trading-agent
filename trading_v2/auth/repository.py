# coding: utf-8
"""Persistent user and opaque session-token storage."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.orm import Mapped, mapped_column
from trading_v2.auth.models import User
from trading_v2.storage.database import Base, Database

def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

class UserRecord(Base):
    __tablename__ = "auth_users_v2"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions_v2"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class AuthRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def user_count(self) -> int:
        with self.database.sessions() as db:
            return int(db.scalar(select(func.count()).select_from(UserRecord)) or 0)

    def create_user(self, username: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc)
        record = UserRecord(id=str(uuid4()), username=username, password_hash=password_hash, created_at=now)
        with self.database.sessions.begin() as db:
            db.add(record)
        return self._user(record)

    def get_user(self, username: str) -> tuple[User, str] | None:
        with self.database.sessions() as db:
            record = db.scalar(select(UserRecord).where(UserRecord.username == username))
            return (self._user(record), record.password_hash) if record else None

    def get_user_by_token(self, token_hash: str) -> User | None:
        now = datetime.now(timezone.utc)
        with self.database.sessions() as db:
            session = db.scalar(select(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash, AuthSessionRecord.expires_at > now))
            record = db.get(UserRecord, session.user_id) if session else None
            return self._user(record) if record else None

    def create_session(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        with self.database.sessions.begin() as db:
            db.add(AuthSessionRecord(token_hash=token_hash, user_id=user_id, expires_at=expires_at, created_at=datetime.now(timezone.utc)))

    def delete_session(self, token_hash: str) -> None:
        with self.database.sessions.begin() as db:
            db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash))

    @staticmethod
    def _user(record: UserRecord) -> User:
        return User(id=record.id, username=record.username, created_at=_aware(record.created_at))
