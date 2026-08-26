import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pytest
from news_pipeline.database import Database, connect, initialize_database


class DatabaseTestCase(unittest.TestCase):
    def test_initialize_database_creates_required_tables(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test_news.db"
            initialize_database(database_path)

            with closing(connect(database_path)) as connection:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()

            table_names = {row["name"] for row in rows}
            self.assertTrue(
                {"raw_news", "clean_news", "analysis_results", "collection_runs"}
                <= table_names
            )


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_news.db"
    return Database(db_file)


def test_raw_and_clean_news_crud(db):
    raw_id = db.save_raw_news({
        "source": "test_source",
        "collection_method": "rss",
        "category": "AI",
        "title": "테스트 뉴스",
        "url": "https://example.com/news1",
        "published_at_raw": "2026-08-24 10:00:00",
        "content_raw": "본문입니다."
    }, policy="upsert")
    assert raw_id is not None

    clean_id = db.save_clean_news({
        "raw_id": raw_id,
        "source": "test_source",
        "category": "AI",
        "title": "테스트 뉴스",
        "canonical_url": "https://example.com/news1",
        "published_at": "2026-08-24 10:00:00",
        "content": "정제된 본문",
        "summary_status": "pending"
    }, policy="upsert")
    assert clean_id is not None

    unsummarized = db.get_unsummarized_news()
    assert len(unsummarized) >= 1

    db.save_summary_result(clean_id, {
        "summary": "요약문",
        "key_points": ["포인트1"],
        "ai_provider": "openai",
        "ai_model": "gpt-5-mini"
    })

    news = db.get_news_by_id(clean_id)
    assert news["summary_status"] == "summarized"
    assert news["ai_provider"] == "openai"


def test_analysis_results_and_counts(db):
    analysis_id = db.save_analysis_result({
        "date_from": "2026-08-24",
        "date_to": "2026-08-24",
        "category": "AI",
        "article_count": 5,
        "trends": ["트렌드"],
        "keywords": ["AI"],
        "ai_provider": "openai",
        "ai_model": "gpt-5-mini",
        "status": "completed"
    })
    assert analysis_id is not None

    detail = db.get_analysis_result(analysis_id)
    assert detail["article_count"] == 5
    assert "트렌드" in detail["trends"]
