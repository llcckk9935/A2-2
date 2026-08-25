from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, call

import pytest
import requests

from news_pipeline.collectors.article_crawler import (
    ArticleCrawler,
    ContentNotFoundError,
    PremiumArticleError,
    RateLimitError,
    RobotsDeniedError,
)
from news_pipeline.models import RawNews


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SELECTORS = {
    "title": ["h1"],
    "content": ["#articleBody", "article"],
    "remove": [".advertisement", ".reporter", "script"],
    "premium": [".paywall", ".premium"],
}


def response(*, text: str, status_code: int = 200) -> Mock:
    result = Mock()
    result.text = text
    result.status_code = status_code
    result.raise_for_status.return_value = None
    return result


def news(url: str = "https://www.inews24.com/view/123") -> RawNews:
    return RawNews(
        source="inews24",
        source_id="123",
        collection_method="rss",
        category="it",
        title="RSS 제목",
        url=url,
        published_at_raw="Mon, 24 Aug 2026 09:00:00 +0900",
        raw_payload={"rss": "original"},
    )


def crawler(session: Mock, *, sleep: Mock | None = None) -> ArticleCrawler:
    return ArticleCrawler(
        timeout=7,
        user_agent="A2-2-Test/1.0",
        selectors=SELECTORS,
        session=session,
        sleep=sleep or Mock(),
    )


def allow_robots() -> Mock:
    return response(text="User-agent: *\nAllow: /")


def test_crawl_extracts_article_content_from_fixture() -> None:
    session = Mock()
    article_html = (FIXTURE_DIR / "sample_article.html").read_text(encoding="utf-8")
    session.get.side_effect = [allow_robots(), response(text=article_html)]

    result = crawler(session).crawl(news(), delay=1.5)

    assert result.collection_method == "crawl"
    assert result.title == "테스트 기사"
    assert result.category == "it"
    assert "첫 번째 기사 문단" in (result.content_raw or "")
    assert "실제 뉴스 사이트에 요청하지 않고" in (result.content_raw or "")
    assert result.raw_payload["rss"] == "original"
    assert result.raw_payload["crawl"]["content_selector"] == "article"
    assert result.collected_at is not None


def test_crawl_applies_timeout_user_agent_and_delay() -> None:
    session = Mock()
    sleep = Mock()
    article_html = (FIXTURE_DIR / "sample_article.html").read_text(encoding="utf-8")
    session.get.side_effect = [allow_robots(), response(text=article_html)]

    crawler(session, sleep=sleep).crawl(news(), delay=2)

    expected_headers = {"User-Agent": "A2-2-Test/1.0"}
    assert session.get.call_args_list == [
        call("https://www.inews24.com/robots.txt", headers=expected_headers, timeout=7),
        call("https://www.inews24.com/view/123", headers=expected_headers, timeout=7),
    ]
    sleep.assert_called_once_with(2)


def test_crawl_does_not_request_article_when_robots_denies_access() -> None:
    session = Mock()
    session.get.return_value = response(text="User-agent: *\nDisallow: /view/")

    with pytest.raises(RobotsDeniedError):
        crawler(session).crawl(news(), delay=0)

    assert session.get.call_count == 1


def test_crawl_skips_premium_article() -> None:
    session = Mock()
    session.get.side_effect = [
        allow_robots(),
        response(text="<html><body><div class='paywall'>premium</div><article>body</article></body></html>"),
    ]

    with pytest.raises(PremiumArticleError):
        crawler(session).crawl(news(), delay=0)


def test_crawl_rejects_page_without_article_content() -> None:
    session = Mock()
    session.get.side_effect = [allow_robots(), response(text="<html><body><h1>제목만 있음</h1></body></html>")]

    with pytest.raises(ContentNotFoundError):
        crawler(session).crawl(news(), delay=0)


def test_crawl_raises_rate_limit_error_for_http_429() -> None:
    session = Mock()
    session.get.side_effect = [allow_robots(), response(text="", status_code=429)]

    with pytest.raises(RateLimitError):
        crawler(session).crawl(news(), delay=0)


def test_crawl_propagates_article_timeout_for_service_to_log_and_continue() -> None:
    session = Mock()
    session.get.side_effect = [allow_robots(), requests.Timeout("요청 시간 초과")]

    with pytest.raises(requests.Timeout):
        crawler(session).crawl(news(), delay=0)


def test_crawl_extracts_page_metadata_and_removes_noise() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="페이지 제목">
      <meta name="author" content="홍길동 기자">
      <meta property="article:published_time" content="2026-08-25T10:00:00+09:00">
      <meta property="article:section" content="it">
    </head><body><div id="articleBody">
      <p>보존할 본문입니다.</p><div class="advertisement">광고 문구</div>
    </div></body></html>
    """
    session = Mock()
    session.get.side_effect = [allow_robots(), response(text=html)]

    result = crawler(session).crawl(news(), delay=0)

    assert result.title == "페이지 제목"
    assert result.published_at_raw == "2026-08-25T10:00:00+09:00"
    assert result.raw_payload["crawl"]["author"] == "홍길동 기자"
    assert result.content_raw == "보존할 본문입니다."

