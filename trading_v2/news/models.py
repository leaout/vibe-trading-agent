# coding: utf-8
"""Normalized financial-news contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trading_v2.domain.enums import AssetClass


class NewsArticle(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=2_000)
    url: str
    source: str
    published_at: datetime
    asset_class: AssetClass
    instrument: str | None = None
    category: str = "market"

    @field_validator("id", "title", "source", "category")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("news text fields cannot be empty")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip().replace("http://", "https://", 1)
        if not normalized.startswith("https://"):
            raise ValueError("news URL must use HTTPS")
        return normalized
