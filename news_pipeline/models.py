"""모듈 사이에서 공유하는 데이터 구조."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


SaveResult = Literal["inserted", "updated", "skipped"]


@dataclass(slots=True)
class RawNews:
    source: str
    collection_method: Literal["rss", "crawl", "rss+crawl"]
    category: str
    title: str
    url: str
    source_id: str | None = None
    published_at_raw: str | None = None
    content_raw: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    collected_at: str | None = None
    id: int | None = None


@dataclass(slots=True)
class CleanNews:
    raw_id: int
    source: str
    category: str
    title: str
    canonical_url: str
    published_at: str | None = None
    content: str | None = None
    summary: str | None = None
    key_points: list[str] = field(default_factory=list)
    summary_status: Literal["pending", "summarized", "failed", "not_ready"] = "pending"
    id: int | None = None


class SummaryResult(BaseModel):
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=2, max_length=3)


class InsightResult(BaseModel):
    trends: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    major_issues: list[str] = Field(min_length=1)
    common_points: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    implications: list[str] = Field(min_length=1)


@dataclass(slots=True)
class AnalysisResult:
    date_from: str | None
    date_to: str | None
    category: str | None
    article_count: int
    insights: InsightResult
    article_ids: list[int] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    ai_provider: str = "mock"
    ai_model: str = "mock-model"
    id: int | None = None
    excluded_count: int = 0


@dataclass(slots=True)
class RunStats:
    requested_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
