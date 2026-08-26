"""뉴스 데이터 정제 및 중복 처리 서비스."""

from __future__ import annotations

import logging
import html
import re
import sqlite3
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from news_pipeline.database import Database
from news_pipeline.models import RunStats


logger = logging.getLogger("cleaning")


def normalize_text(text: Optional[str]) -> str:
    """HTML 태그 제거 및 텍스트 정규화"""
    if not text:
        return ""
    # RSS와 기사 메타데이터의 HTML 엔티티를 실제 문자로 복원한다.
    text = html.unescape(text)
    # HTML 태그 제거
    clean = re.sub(r"<[^>]+>", "", text)
    # 불필요한 공백 정리
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_url(url: str) -> str:
    """마케팅 추적 파라미터(utm_, fbclid 등) 및 fragment 제거"""
    if not url:
        return ""
    parsed = urlparse(url)
    query_params = []
    if parsed.query:
        for param in parsed.query.split("&"):
            if not param.startswith(("utm_", "fbclid", "gclid", "NaPm", "hsCtaTracking")):
                query_params.append(param)
    new_query = "&".join(query_params)
    
    clean_parsed = parsed._replace(query=new_query, fragment="")
    return urlunparse(clean_parsed)


def normalize_published_at(value: Optional[str]) -> Optional[str]:
    """RSS/ISO 날짜를 시간대가 포함된 ISO 8601 문자열로 통일한다."""
    if not value or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("지원하지 않는 발행일 형식이라 결측값으로 처리합니다: %s", raw)
            return None
    return parsed.isoformat()


def clean_news_item(raw_data: dict) -> dict:
    """raw 뉴스 데이터를 받아 clean 뉴스 데이터로 변환"""
    title = normalize_text(raw_data.get("title"))
    content = normalize_text(raw_data.get("content_raw"))
    canonical_url = normalize_url(raw_data.get("url"))

    return {
        "raw_id": raw_data.get("id"),
        "source": raw_data.get("source"),
        "category": raw_data.get("category"),
        "title": title,
        "canonical_url": canonical_url,
        "published_at": normalize_published_at(raw_data.get("published_at_raw")),
        "content": content,
        "summary_status": "pending",
    }


class CleaningService:
    """DB의 raw 뉴스를 정제해 clean 뉴스로 저장한다."""

    def __init__(self, database_path: str | Path):
        self.database = Database(database_path)

    def clean(
        self,
        *,
        include_cleaned: bool = False,
        limit: int | None = None,
        duplicate_policy: str = "skip",
    ) -> RunStats:
        if duplicate_policy not in {"skip", "upsert"}:
            raise ValueError("duplicate_policy는 skip 또는 upsert여야 합니다.")

        rows = self.database.list_raw_news(
            include_cleaned=include_cleaned,
            limit=limit,
        )
        stats = RunStats(requested_count=len(rows))

        for row in rows:
            existing = self.database.get_clean_news_by_raw_id(row["id"])
            if existing is not None and duplicate_policy == "skip":
                stats.duplicate_count += 1
                stats.skipped_count += 1
                continue

            try:
                cleaned = clean_news_item(row)
                if not cleaned["title"]:
                    raise ValueError("정제 후 제목이 비어 있습니다.")
                if not cleaned["canonical_url"]:
                    raise ValueError("정제 후 URL이 비어 있습니다.")
                self.database.save_clean_news(cleaned, policy=duplicate_policy)
                stats.success_count += 1
            except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
                stats.failure_count += 1
                logger.error("raw_news ID=%s 정제 실패: %s", row.get("id"), exc)

        return stats
