# coding: utf-8
"""Validated model output and persisted decision projections."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trading_v2.domain.enums import DecisionAction


class DecisionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: DecisionAction
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1_000)

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        return value.strip()


class ModelDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    signal_id: str
    session_id: str
    strategy_version: int
    action: DecisionAction
    confidence: float
    rationale: str
    model_provider: str
    model_name: str
    prompt_version: str
    status: Literal["completed", "fallback"]
    error: str | None = None
    created_at: datetime
