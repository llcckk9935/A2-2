import contextlib
import io
import json

from news_pipeline.cli import run_cli
from news_pipeline.database import Database
from news_pipeline.services.cleaning import (
    CleaningService,
    normalize_published_at,
    normalize_text,
    normalize_url,
)


def test_normalize_text():
    html_text = "<p>  안녕하세요!   <b>뉴스</b>입니다. </p>"
    assert normalize_text(html_text) == "안녕하세요! 뉴스입니다."


def test_normalize_text_decodes_html_entities():
    assert normalize_text("&quot;AI&quot;&hellip;반도체&middot;클라우드") == '"AI"…반도체·클라우드'


def test_normalize_url():
    tracking_url = "https://example.com/news?utm_source=naver&fbclid=12345&id=7"
    canonical = normalize_url(tracking_url)
    assert "utm_source" not in canonical
    assert "fbclid" not in canonical
    assert canonical == "https://example.com/news?id=7"


def test_normalize_published_at_supports_rss_and_iso_dates():
    assert normalize_published_at("Wed, 26 Aug 2026 12:00:00 +0900") == (
        "2026-08-26T12:00:00+09:00"
    )
    assert normalize_published_at("2026-08-26T12:00:00Z") == (
        "2026-08-26T12:00:00+00:00"
    )
    assert normalize_published_at("잘못된 날짜") is None


def _save_raw(database: Database, *, title="<b>테스트 뉴스</b>", content="<p>본문</p>"):
    return database.save_raw_news(
        {
            "source": "test",
            "collection_method": "rss",
            "category": "it",
            "title": title,
            "url": "https://example.com/news?utm_source=test&id=1#section",
            "published_at_raw": "2026-08-26T12:00:00",
            "content_raw": content,
        }
    )


def test_cleaning_service_reads_raw_and_saves_clean_news(tmp_path):
    database_path = tmp_path / "news.db"
    database = Database(database_path)
    raw_id = _save_raw(database)

    stats = CleaningService(database_path).clean()

    assert stats.requested_count == 1
    assert stats.success_count == 1
    clean = database.get_clean_news_by_raw_id(raw_id)
    assert clean["title"] == "테스트 뉴스"
    assert clean["content"] == "본문"
    assert clean["canonical_url"] == "https://example.com/news?id=1"
    assert clean["summary_status"] == "pending"


def test_cleaning_service_skip_and_upsert_policies(tmp_path):
    database_path = tmp_path / "news.db"
    database = Database(database_path)
    raw_id = _save_raw(database)
    service = CleaningService(database_path)
    service.clean()

    skipped = service.clean(include_cleaned=True, duplicate_policy="skip")
    assert skipped.requested_count == 1
    assert skipped.success_count == 0
    assert skipped.duplicate_count == 1
    assert skipped.skipped_count == 1

    database.save_raw_news(
        {
            "source": "test",
            "collection_method": "rss",
            "category": "it",
            "title": "수정된 제목",
            "url": "https://example.com/news?utm_source=test&id=1#section",
            "content_raw": "수정된 본문",
        },
        policy="upsert",
    )
    updated = service.clean(include_cleaned=True, duplicate_policy="upsert")
    assert updated.success_count == 1
    assert database.get_clean_news_by_raw_id(raw_id)["title"] == "수정된 제목"


def test_clean_cli_runs_full_database_pipeline(tmp_path):
    config = {
        "app": {"name": "test", "timezone": "Asia/Seoul"},
        "database": {"path": "data/test.db"},
        "news": {
            "default_source": "test",
            "default_limit": 20,
            "request_timeout_seconds": 10,
            "crawl_delay_seconds": 0,
            "user_agent": "test",
            "duplicate_policy": "skip",
            "categories": ["it"],
            "sources": {
                "test": {
                    "base_url": "https://example.com",
                    "rss_urls": {},
                }
            },
        },
        "ai": {"provider": "mock"},
        "report": {"output_directory": "reports"},
        "export": {"output_directory": "exports"},
        "logging": {"file": "logs/app.log"},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    database = Database(tmp_path / "data/test.db")
    raw_id = _save_raw(database)

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = run_cli(["--config", str(config_path), "clean", "--all"])

    assert exit_code == 0
    assert "대상=1" in output.getvalue()
    assert "성공=1" in output.getvalue()
    assert database.get_clean_news_by_raw_id(raw_id) is not None
