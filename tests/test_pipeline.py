"""외부 네트워크와 실제 AI 비용 없이 전체 파이프라인을 검증한다."""

from dataclasses import replace
from pathlib import Path

from news_pipeline.config import load_config
from news_pipeline.database import Database
from news_pipeline.models import RawNews, RunStats
from news_pipeline.providers.mock_provider import MockAIProvider
from news_pipeline.services.analyzer import AnalyzerService
from news_pipeline.services.cleaning import CleaningService
from news_pipeline.services.collection_service import CollectionService
from news_pipeline.services.exporter import ExporterService
from news_pipeline.services.reporter import ReporterService
from news_pipeline.services.summarizer import SummarizerService


class FixtureRSSCollector:
    source = "fixture"

    def __init__(self) -> None:
        self.last_stats = RunStats()
        self.last_errors: list[str] = []

    def fetch(self, category: str, limit: int) -> list[RawNews]:
        items = [
            RawNews(
                source="fixture",
                source_id="1",
                collection_method="rss",
                category="it",
                title="&quot;AI&quot; 반도체 뉴스",
                url="https://example.com/it",
                published_at_raw="2026-08-26T10:00:00+09:00",
            ),
            RawNews(
                source="fixture",
                source_id="2",
                collection_method="rss",
                category="economy",
                title="경제 정책 뉴스",
                url="https://example.com/economy",
                published_at_raw="2026-08-26T11:00:00+09:00",
            ),
        ]
        return items[:limit]


class FixtureArticleCrawler:
    def crawl(self, news: RawNews, delay: float) -> RawNews:
        return replace(
            news,
            collection_method="crawl",
            content_raw=f"{news.title}의 충분한 테스트 기사 본문입니다.",
        )


def test_complete_mock_pipeline_creates_all_required_outputs(tmp_path):
    config, _ = load_config(Path(__file__).parents[1] / "config.json")
    database_path = tmp_path / "data" / "news.db"
    config = config.model_copy(
        update={
            "database": config.database.model_copy(update={"path": str(database_path)}),
            "report": config.report.model_copy(
                update={"output_directory": str(tmp_path / "reports")}
            ),
            "export": config.export.model_copy(
                update={"output_directory": str(tmp_path / "exports")}
            ),
        }
    )
    database = Database(database_path)

    collected = CollectionService(
        database, FixtureRSSCollector(), FixtureArticleCrawler()
    ).fetch(
        method="all",
        category="all",
        limit=2,
        delay=0,
        duplicate_policy="upsert",
        published_date=None,
    )
    assert collected.success_count == 2
    assert all(row["content_raw"] for row in database.list_raw_news(include_cleaned=True))

    cleaned = CleaningService(database_path).clean(duplicate_policy="upsert")
    assert cleaned.success_count == 2
    assert database.list_news(limit=None)[1]["title"] == '"AI" 반도체 뉴스'

    provider = MockAIProvider(config.ai)
    summarized = SummarizerService(
        database_path, config.ai, provider
    ).summarize(
        news_id=None,
        all_news=False,
        unsummarized=True,
        limit=2,
        force=False,
    )
    assert summarized.success_count == 2

    analysis = AnalyzerService(
        database_path, config.ai, config.analysis, provider
    ).analyze(date_from=None, date_to=None, category=None, limit=2)
    assert analysis is not None
    assert analysis.article_count == 2
    assert AnalyzerService(
        database_path, config.ai, config.analysis, provider
    ).get_result(analysis.id) is not None

    report_paths = ReporterService(
        database_path,
        output_directory=tmp_path / "reports",
        chart_dpi=config.report.chart_dpi,
    ).generate(
        date_from=None,
        date_to=None,
        category=None,
        top_n=5,
        output_format="md",
        output=None,
    )
    assert len(report_paths) == 3
    assert all(path.exists() for path in report_paths)
    report_text = report_paths[-1].read_text(encoding="utf-8")
    assert "정제 성공률" in report_text
    assert "카테고리별 TOP N" in report_text
    assert "Mock" in report_text

    exporter = ExporterService()
    for output_format in ("csv", "jsonl", "xlsx"):
        path = exporter.export(
            output_format=output_format,
            status="summarized",
            category="all",
            date_from=None,
            date_to=None,
            output=None,
            config=config,
            project_root=tmp_path,
        )
        assert path.exists()
        assert path.stat().st_size > 0
