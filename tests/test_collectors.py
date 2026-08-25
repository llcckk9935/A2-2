from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from news_pipeline.collectors.rss_collector import RSSCollector


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def make_response(content: bytes) -> Mock:
    response = Mock()
    response.content = content
    response.raise_for_status.return_value = None
    return response


def make_collector(session: Mock, rss_urls: dict[str, str] | None = None) -> RSSCollector:
    return RSSCollector(
        source="inews24",
        rss_urls=rss_urls or {"it": "https://example.com/it.xml"},
        timeout=7,
        user_agent="A2-2-Test/1.0",
        session=session,
    )


def test_fetch_maps_rss_item_to_raw_news() -> None:
    session = Mock()
    session.get.return_value = make_response((FIXTURE_DIR / "sample_rss.xml").read_bytes())

    collector = make_collector(session)
    result = collector.fetch("IT", limit=5)

    assert len(result) == 1
    news = result[0]
    assert news.source == "inews24"
    assert news.source_id == "sample-1"
    assert news.collection_method == "rss"
    assert news.category == "it"
    assert news.title == "AI 반도체 시장 경쟁 본격화"
    assert news.url == "https://example.com/news/1"
    assert news.content_raw == "테스트를 위한 가상 뉴스 설명입니다."
    assert news.published_at_raw == "Sat, 22 Aug 2026 09:00:00 +0900"
    assert news.collected_at is not None
    assert news.raw_payload["link"] == news.url


def test_fetch_applies_timeout_and_user_agent() -> None:
    session = Mock()
    session.get.return_value = make_response((FIXTURE_DIR / "sample_rss.xml").read_bytes())
    collector = make_collector(session)

    collector.fetch("it", limit=1)

    session.get.assert_called_once_with(
        "https://example.com/it.xml",
        headers={"User-Agent": "A2-2-Test/1.0"},
        timeout=7,
    )


def test_fetch_all_continues_when_one_feed_times_out() -> None:
    session = Mock()
    valid_response = make_response((FIXTURE_DIR / "sample_rss.xml").read_bytes())
    session.get.side_effect = [requests.Timeout("요청 시간 초과"), valid_response]
    collector = make_collector(
        session,
        {
            "politics": "https://example.com/politics.xml",
            "it": "https://example.com/it.xml",
        },
    )

    result = collector.fetch("all", limit=10)

    assert [news.category for news in result] == ["it"]
    assert collector.last_stats.success_count == 1
    assert collector.last_stats.failure_count == 1
    assert len(collector.last_errors) == 1


def test_fetch_never_returns_more_than_limit() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>test</title>
      <item><guid>1</guid><title>one</title><link>https://example.com/1</link></item>
      <item><guid>2</guid><title>two</title><link>https://example.com/2</link></item>
    </channel></rss>"""
    session = Mock()
    session.get.return_value = make_response(xml)

    result = make_collector(session).fetch("it", limit=1)

    assert len(result) == 1
    assert result[0].source_id == "1"


def test_fetch_preserves_html_in_raw_content() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>test</title>
      <item><guid>html</guid><title>html content</title>
      <link>https://example.com/html</link>
      <description><![CDATA[<p>raw <strong>content</strong></p>]]></description></item>
    </channel></rss>"""
    session = Mock()
    session.get.return_value = make_response(xml)

    result = make_collector(session).fetch("it", limit=1)

    assert result[0].content_raw == "<p>raw <strong>content</strong></p>"


def test_fetch_skips_invalid_item_and_keeps_valid_item() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>test</title>
      <item><guid>bad</guid><title>missing link</title></item>
      <item><guid>good</guid><title>valid</title><link>https://example.com/good</link></item>
    </channel></rss>"""
    session = Mock()
    session.get.return_value = make_response(xml)
    collector = make_collector(session)

    result = collector.fetch("it", limit=10)

    assert [news.source_id for news in result] == ["good"]
    assert collector.last_stats.failure_count == 1


def test_fetch_rejects_category_without_configured_url() -> None:
    collector = make_collector(Mock())

    with pytest.raises(ValueError, match="RSS 주소가 없는 카테고리"):
        collector.fetch("politics", limit=1)
