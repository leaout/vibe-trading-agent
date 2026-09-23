# coding: utf-8
"""Password hashing and opaque-cookie authentication service."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from trading_v2.auth.models import User
from trading_v2.auth.repository import AuthRepository

_ITERATIONS = 310_000

class AuthService:
    def __init__(self, repository: AuthRepository, session_ttl_hours: int = 168) -> None:
        self.repository = repository
        self.session_ttl = timedelta(hours=session_ttl_hours)

    async def initialize(self) -> None:
        import asyncio
        await asyncio.to_thread(self.repository.database.create_schema)

    def can_register_first_user(self) -> bool:
        return self.repository.user_count() == 0

    def register(self, username: str, password: str) -> tuple[User, str]:
        username = username.strip().lower()
        if not self.can_register_first_user():
            raise ValueError("首次注册已完成，请使用登录")
        user = self.repository.create_user(username, self.hash_password(password))
        return user, self.issue_token(user.id)

    def authenticate(self, username: str, password: str) -> tuple[User, str] | None:
        found = self.repository.get_user(username.strip().lower())
        if found is None:
            return None
        user, stored = found
        return (user, self.issue_token(user.id)) if self.verify_password(password, stored) else None

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(48)
        self.repository.create_session(hashlib.sha256(token.encode()).hexdigest(), user_id, datetime.now(timezone.utc) + self.session_ttl)
        return token

    def user_from_token(self, token: str | None) -> User | None:
        return self.repository.get_user_by_token(hashlib.sha256(token.encode()).hexdigest()) if token else None

    def revoke_token(self, token: str | None) -> None:
        if token:
            self.repository.delete_session(hashlib.sha256(token.encode()).hexdigest())

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
        return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
            return algorithm == "pbkdf2_sha256" and hmac.compare_digest(candidate.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
