from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

from news_pipeline.database import Database
from news_pipeline.models import RawNews, RunStats
from news_pipeline.services.collection_service import CollectionService


def _news(url: str = "https://example.com/article?utm_source=test") -> RawNews:
    return RawNews(
        source="test",
        collection_method="rss",
        category="it",
        title="테스트 기사",
        url=url,
        content_raw="RSS 본문",
        collected_at=datetime.now(timezone.utc).isoformat(),
    )


def _service(tmp_path, items: list[RawNews]) -> tuple[CollectionService, Database, Mock]:
    database = Database(tmp_path / "news.db")
    rss = Mock()
    rss.source = "test"
    rss.fetch.return_value = items
    rss.last_stats = RunStats(requested_count=len(items), success_count=len(items))
    rss.last_errors = []
    crawler = Mock()
    return CollectionService(database, rss, crawler), database, crawler


def test_rss_fetch_saves_raw_news_and_collection_run(tmp_path) -> None:
    service, database, _ = _service(tmp_path, [_news()])

    stats = service.fetch("rss", "it", 1, 0, "skip")

    assert stats.success_count == 1
    assert database.get_raw_news_by_url("https://example.com/article") is not None
    with database.get_connection() as connection:
        run = connection.execute("SELECT * FROM collection_runs").fetchone()
    assert run["status"] == "completed"
    assert run["success_count"] == 1


def test_skip_policy_counts_existing_url_as_duplicate(tmp_path) -> None:
    service, database, _ = _service(tmp_path, [_news()])
    service.fetch("rss", "it", 1, 0, "skip")

    stats = service.fetch("rss", "it", 1, 0, "skip")

    assert stats.success_count == 0
    assert stats.duplicate_count == 1
    assert stats.skipped_count == 1
    assert len(database.list_raw_news(include_cleaned=True)) == 1


def test_all_method_saves_crawled_result_as_rss_plus_crawl(tmp_path) -> None:
    seed = _news("https://example.com/article")
    service, database, crawler = _service(tmp_path, [seed])
    crawler.crawl.return_value = RawNews(
        source="test",
        collection_method="crawl",
        category="it",
        title="크롤링 기사",
        url=seed.url,
        content_raw="기사 전문",
        collected_at=seed.collected_at,
    )

    stats = service.fetch("all", "it", 1, 0, "upsert")

    assert stats.success_count == 1
    stored = database.get_raw_news_by_url(seed.url)
    assert stored["collection_method"] == "rss+crawl"
    assert stored["content_raw"] == "기사 전문"
