"""RSS 수집과 기사 크롤링을 조정하는 서비스.

Collector는 HTTP 요청과 파싱 후 ``RawNews``를 반환하고, 이 서비스는
수집 순서·처리 제한·요청 지연·중복 정책·저장·실행 통계를 조정한다.
중복은 정규화된 URL로 판단하며 이 서비스가 ``skip`` 또는 ``upsert`` 정책을
선택하고, 실제 조회와 저장 SQL은 ``database.py``에 위임한다. 기사별 실패는
로그에 남긴 뒤 가능한 경우 다음 기사를 계속 처리하고, 실행 단위 집계와
대표 오류는 ``collection_runs``에 기록한다. 최초 오류를 대표 오류로 삼고
추가 오류가 있으면 ``(외 N건)``을 덧붙인다. 정상 0건과 전체 중복은
``completed``, 일부 실패는 ``partial``, 요청·파싱 또는 전체 처리가 실패하면
``failed``로 처리한다.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, replace
from datetime import date
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from news_pipeline.collectors.article_crawler import ArticleCrawler, CrawlError
from news_pipeline.collectors.rss_collector import RSSCollector
from news_pipeline.database import Database
from news_pipeline.models import RawNews, RunStats


LOGGER = logging.getLogger(__name__)


class CollectionService:
    def __init__(
        self,
        database: Database,
        rss_collector: RSSCollector,
        article_crawler: ArticleCrawler,
    ) -> None:
        self.database = database
        self.rss_collector = rss_collector
        self.article_crawler = article_crawler

    def fetch(
        self,
        method: str,
        category: str,
        limit: int,
        delay: float,
        duplicate_policy: Literal["skip", "upsert"],
        published_date: str | None = None,
    ) -> RunStats:
        """뉴스를 수집하고 raw 저장소에 저장한 뒤 실행 통계를 반환한다."""

        if method not in {"rss", "crawl", "all"}:
            raise ValueError(f"지원하지 않는 수집 방식입니다: {method}")
        if duplicate_policy not in {"skip", "upsert"}:
            raise ValueError(f"지원하지 않는 중복 정책입니다: {duplicate_policy}")

        stats = RunStats(requested_count=limit)
        errors: list[str] = []
        run_id = self.database.start_collection_run(
            source=self.rss_collector.source,
            collection_method=method,
            category=category,
            requested_count=limit,
        )

        try:
            seeds = self.rss_collector.fetch(category, limit)
            stats.failure_count += self.rss_collector.last_stats.failure_count
            errors.extend(self.rss_collector.last_errors)
            if published_date:
                seeds = [item for item in seeds if _matches_date(item, published_date)]

            for seed in seeds:
                news = seed
                if method in {"crawl", "all"}:
                    try:
                        news = self.article_crawler.crawl(seed, delay)
                        if method == "all":
                            news = replace(news, collection_method="rss+crawl")
                    except (CrawlError, requests.RequestException, ValueError) as exc:
                        stats.failure_count += 1
                        errors.append(str(exc))
                        LOGGER.warning("기사 본문 수집 실패 후 처리 계속: url=%s error=%s", seed.url, exc)
                        if method == "crawl":
                            continue
                        news = seed

                self._save(news, duplicate_policy, stats, errors)
        except (ValueError, OSError) as exc:
            stats.failure_count += 1
            errors.append(str(exc))
            LOGGER.error("뉴스 수집 실행 실패: %s", exc)

        status = _run_status(stats)
        self.database.finish_collection_run(
            run_id,
            success_count=stats.success_count,
            failure_count=stats.failure_count,
            duplicate_count=stats.duplicate_count,
            status=status,
            error_message=_representative_error(errors),
        )
        return stats

    def _save(
        self,
        news: RawNews,
        duplicate_policy: Literal["skip", "upsert"],
        stats: RunStats,
        errors: list[str],
    ) -> None:
        normalized = replace(news, url=_normalize_url(news.url))
        existing = self.database.get_raw_news_by_url(normalized.url)
        if existing is not None:
            stats.duplicate_count += 1
            if duplicate_policy == "skip":
                stats.skipped_count += 1
                return

        try:
            self.database.save_raw_news(asdict(normalized), policy=duplicate_policy)
            stats.success_count += 1
        except Exception as exc:
            stats.failure_count += 1
            errors.append(str(exc))
            LOGGER.error("raw 뉴스 저장 실패: url=%s error=%s", normalized.url, exc)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_")]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def _matches_date(news: RawNews, expected: str) -> bool:
    raw = news.published_at_raw
    if not raw:
        return False
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(raw).date() == date.fromisoformat(expected)
    except (TypeError, ValueError, OverflowError):
        return raw[:10] == expected


def _run_status(stats: RunStats) -> str:
    if stats.failure_count == 0:
        return "completed"
    if stats.success_count or stats.skipped_count:
        return "partial"
    return "failed"


def _representative_error(errors: list[str]) -> str | None:
    if not errors:
        return None
    suffix = f" (외 {len(errors) - 1}건)" if len(errors) > 1 else ""
    return f"{errors[0]}{suffix}"
