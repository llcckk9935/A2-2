"""robots.txt를 준수하며 아이뉴스24 기사 본문을 추출한다."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag

from news_pipeline.models import RawNews


LOGGER = logging.getLogger(__name__)


class CrawlError(RuntimeError):
    """기사 크롤링을 완료할 수 없을 때 발생한다."""


class RobotsDeniedError(CrawlError):
    """robots.txt가 기사 접근을 허용하지 않을 때 발생한다."""


class ContentNotFoundError(CrawlError):
    """본문 선택자에서 유효한 기사 내용을 찾지 못했을 때 발생한다."""


class PremiumArticleError(CrawlError):
    """유료 또는 프리미엄 기사로 판단될 때 발생한다."""


class RateLimitError(CrawlError):
    """서버가 HTTP 429로 요청 중단을 요구할 때 발생한다."""


class ArticleCrawler:
    """RSS에서 얻은 기사 URL을 요청하여 본문과 메타데이터를 보완한다."""

    def __init__(
        self,
        *,
        timeout: float,
        user_agent: str,
        selectors: Mapping[str, Sequence[str]],
        respect_robots_txt: bool = True,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.selectors = {key: list(value) for key, value in selectors.items()}
        self.respect_robots_txt = respect_robots_txt
        self.session = session or requests.Session()
        self.sleep = sleep
        self._robots_cache: dict[str, RobotFileParser | bool] = {}
        self._has_requested = False

    def crawl(self, news: RawNews, delay: float) -> RawNews:
        """기사 본문을 추출한 새 ``RawNews`` 객체를 반환한다."""

        if delay < 0:
            raise ValueError("delay는 0 이상이어야 합니다.")
        parsed_url = urlsplit(news.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"올바르지 않은 기사 URL입니다: {news.url}")

        LOGGER.info("기사 크롤링 시작: url=%s", news.url)
        if self.respect_robots_txt and not self._can_fetch(news.url, delay):
            LOGGER.warning("robots.txt에 의해 접근 차단: url=%s", news.url)
            raise RobotsDeniedError(f"robots.txt가 접근을 허용하지 않습니다: {news.url}")

        response = self._request(news.url, delay)
        if response.status_code == 429:
            LOGGER.warning("HTTP 429로 추가 요청 중단 필요: url=%s", news.url)
            raise RateLimitError(f"HTTP 429 Too Many Requests: {news.url}")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        if self._matches_any(soup, self.selectors.get("premium", [])):
            LOGGER.warning("유료 또는 프리미엄 기사 제외: url=%s", news.url)
            raise PremiumArticleError(f"유료 또는 프리미엄 기사입니다: {news.url}")

        title = self._extract_title(soup) or news.title
        content = self._extract_content(soup)
        if not content:
            LOGGER.warning("기사 본문 추출 실패: url=%s", news.url)
            raise ContentNotFoundError(f"기사 본문을 찾을 수 없습니다: {news.url}")

        published_at = self._extract_meta(
            soup,
            ("article:published_time", "date", "pubdate", "datePublished"),
        ) or news.published_at_raw
        author = self._extract_meta(soup, ("author", "article:author"))
        category = self._extract_meta(soup, ("article:section", "section")) or news.category
        raw_payload = dict(news.raw_payload)
        raw_payload["crawl"] = {
            "author": author,
            "published_at": published_at,
            "category": category,
            "content_selector": self._matched_content_selector(soup),
        }

        LOGGER.info("기사 크롤링 성공: url=%s content_length=%d", news.url, len(content))
        return RawNews(
            id=news.id,
            source=news.source,
            source_id=news.source_id,
            collection_method="crawl",
            category=category,
            title=title,
            url=news.url,
            published_at_raw=published_at,
            content_raw=content,
            raw_payload=raw_payload,
            collected_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

    def _request(self, url: str, delay: float) -> requests.Response:
        if self._has_requested and delay:
            self.sleep(delay)
        response = self.session.get(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        self._has_requested = True
        return response

    def _can_fetch(self, article_url: str, delay: float) -> bool:
        parts = urlsplit(article_url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        cached = self._robots_cache.get(origin)
        if isinstance(cached, RobotFileParser):
            return cached.can_fetch(self.user_agent, article_url)
        if isinstance(cached, bool):
            return cached

        robots_url = f"{origin}/robots.txt"
        try:
            response = self._request(robots_url, delay)
            if response.status_code in {401, 403, 429} or response.status_code >= 500:
                self._robots_cache[origin] = False
                return False
            if response.status_code == 404:
                self._robots_cache[origin] = True
                return True
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("robots.txt 확인 실패로 크롤링 중단: url=%s error=%s", robots_url, exc)
            self._robots_cache[origin] = False
            return False

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        self._robots_cache[origin] = parser
        return parser.can_fetch(self.user_agent, article_url)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        meta_title = self._extract_meta(soup, ("og:title", "twitter:title"))
        if meta_title:
            return meta_title
        for selector in self.selectors.get("title", []):
            element = soup.select_one(selector)
            if element and element.get_text(" ", strip=True):
                return element.get_text(" ", strip=True)
        return soup.title.get_text(" ", strip=True) if soup.title else ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        for selector in self.selectors.get("content", []):
            element = soup.select_one(selector)
            if not element:
                continue
            for unwanted_selector in self.selectors.get("remove", []):
                for unwanted in element.select(unwanted_selector):
                    unwanted.decompose()
            paragraphs = [
                paragraph.get_text(" ", strip=True)
                for paragraph in element.select("p")
                if paragraph.get_text(" ", strip=True)
            ]
            text = "\n".join(paragraphs) or element.get_text(" ", strip=True)
            if text.strip():
                return text.strip()
        return ""

    def _matched_content_selector(self, soup: BeautifulSoup) -> str | None:
        for selector in self.selectors.get("content", []):
            if soup.select_one(selector):
                return selector
        return None

    @staticmethod
    def _matches_any(soup: BeautifulSoup, selectors: Sequence[str]) -> bool:
        return any(soup.select_one(selector) is not None for selector in selectors)

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, keys: Sequence[str]) -> str | None:
        for key in keys:
            element: Tag | None = soup.find("meta", attrs={"property": key})
            if element is None:
                element = soup.find("meta", attrs={"name": key})
            if element and element.get("content"):
                return str(element["content"]).strip() or None
        return None
