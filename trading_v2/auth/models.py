# coding: utf-8
"""Authentication request and response contracts."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class User(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    username: str
    created_at: datetime

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)

class AuthStatus(BaseModel):
    authenticated: bool
    user: User | None = None
