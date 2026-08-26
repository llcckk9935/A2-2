"""아이뉴스24 RSS 응답을 공통 ``RawNews`` 모델로 변환한다."""

from __future__ import annotations

import hashlib
import html
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

from news_pipeline.models import RawNews, RunStats


LOGGER = logging.getLogger(__name__)


class RSSCollector:
    """설정에 등록된 RSS 피드를 순차적으로 요청하고 파싱한다.

    HTTP 세션을 생성자에서 주입할 수 있어 단위 테스트에서는 실제 뉴스
    사이트에 접속하지 않는다. ``category='all'``인 경우 한 피드가 실패해도
    나머지 피드를 계속 처리하고, 결과는 카테고리별로 번갈아 선택한다.
    """

    def __init__(
        self,
        *,
        source: str,
        rss_urls: Mapping[str, str],
        timeout: float,
        user_agent: str,
        session: requests.Session | None = None,
    ) -> None:
        self.source = source
        self.rss_urls = {key.lower(): value for key, value in rss_urls.items()}
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = session or requests.Session()
        self.last_stats = RunStats()
        self.last_errors: list[str] = []

    def fetch(self, category: str, limit: int) -> list[RawNews]:
        """RSS에서 최대 ``limit``건을 가져온다.

        요청 또는 파싱 실패는 로그와 ``last_stats``에 기록하고 빈 결과 또는
        정상 처리된 다른 카테고리 결과를 반환한다.
        """

        if limit <= 0:
            raise ValueError("limit은 0보다 커야 합니다.")

        normalized_category = category.lower()
        if normalized_category == "all":
            categories = [name for name, url in self.rss_urls.items() if url.strip()]
        elif normalized_category in self.rss_urls and self.rss_urls[normalized_category].strip():
            categories = [normalized_category]
        else:
            raise ValueError(f"RSS 주소가 없는 카테고리입니다: {category}")

        self.last_stats = RunStats(requested_count=limit)
        self.last_errors = []
        items_by_category: dict[str, list[RawNews]] = {}

        LOGGER.info(
            "RSS 수집 시작: source=%s category=%s limit=%d",
            self.source,
            normalized_category,
            limit,
        )
        for feed_category in categories:
            try:
                items = self._fetch_category(feed_category)
            except (requests.RequestException, ValueError) as exc:
                message = f"{feed_category} RSS 수집 실패: {exc}"
                self.last_errors.append(message)
                self.last_stats.failure_count += 1
                LOGGER.warning(message)
                continue

            items_by_category[feed_category] = items
            LOGGER.info("RSS 카테고리 수집 완료: category=%s count=%d", feed_category, len(items))

        results = self._take_round_robin(items_by_category, limit)
        self.last_stats.success_count = len(results)
        LOGGER.info(
            "RSS 수집 종료: success=%d failure=%d",
            self.last_stats.success_count,
            self.last_stats.failure_count,
        )
        return results

    def _fetch_category(self, category: str) -> list[RawNews]:
        response = self.session.get(
            self.rss_urls[category],
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        response.raise_for_status()

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(f"RSS XML 파싱 오류: {parsed.bozo_exception}")
        if parsed.bozo:
            LOGGER.warning("RSS 일부 파싱 경고: category=%s error=%s", category, parsed.bozo_exception)

        collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        items: list[RawNews] = []
        seen_urls: set[str] = set()
        for entry in parsed.entries:
            try:
                news = self._to_raw_news(entry, category, collected_at)
            except ValueError as exc:
                self.last_stats.failure_count += 1
                LOGGER.warning("RSS 항목 제외: category=%s error=%s", category, exc)
                continue
            if news.url in seen_urls:
                self.last_stats.duplicate_count += 1
                continue
            seen_urls.add(news.url)
            items.append(news)
        return items

    def _to_raw_news(
        self,
        entry: Mapping[str, Any],
        category: str,
        collected_at: str,
    ) -> RawNews:
        title = _plain_text(entry.get("title"))
        url = str(entry.get("link") or "").strip()
        parsed_url = urlsplit(url)
        if not title or parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("필수 필드(title 또는 url)가 없습니다.")

        published_at_raw = str(entry.get("published") or entry.get("updated") or "").strip() or None
        content_raw = _entry_content(entry)
        supplied_id = str(entry.get("id") or "").strip()
        source_id = supplied_id or hashlib.sha256(url.encode("utf-8")).hexdigest()
        raw_payload = {
            "id": supplied_id or None,
            "title": title,
            "link": url,
            "published": published_at_raw,
            "description": content_raw,
            "tags": [
                str(tag.get("term"))
                for tag in entry.get("tags", [])
                if isinstance(tag, Mapping) and tag.get("term")
            ],
        }
        return RawNews(
            source=self.source,
            source_id=source_id,
            collection_method="rss",
            category=category,
            title=title,
            url=url,
            published_at_raw=published_at_raw,
            content_raw=content_raw,
            raw_payload=raw_payload,
            collected_at=collected_at,
        )

    @staticmethod
    def _take_round_robin(
        items_by_category: Mapping[str, list[RawNews]],
        limit: int,
    ) -> list[RawNews]:
        results: list[RawNews] = []
        indexes = {category: 0 for category in items_by_category}
        while len(results) < limit:
            added = False
            for category, items in items_by_category.items():
                index = indexes[category]
                if index >= len(items):
                    continue
                results.append(items[index])
                indexes[category] += 1
                added = True
                if len(results) == limit:
                    break
            if not added:
                break
        return results


def _entry_content(entry: Mapping[str, Any]) -> str | None:
    contents = entry.get("content") or []
    if contents and isinstance(contents[0], Mapping):
        value = contents[0].get("value")
    else:
        value = entry.get("summary") or entry.get("description")
    text = str(value).strip() if value is not None else ""
    return text or None


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    parsed = BeautifulSoup(html.unescape(str(value)), "html.parser").get_text(" ")
    return " ".join(parsed.split())
