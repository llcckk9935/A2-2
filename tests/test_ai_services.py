import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from news_pipeline.config import AIConfig, AnalysisConfig
from news_pipeline.database import connect, initialize_database
from news_pipeline.providers.base import ProviderTimeoutError
from news_pipeline.providers.mock_provider import MockAIProvider
from news_pipeline.services.analyzer import AnalyzerService
from news_pipeline.services.summarizer import SummarizerService


def seed_clean_news(database_path: Path, *, content: str | None, status: str = "pending", summary: str | None = None, category: str = "it", url: str = "https://example.com/1", published_at: str = "2026-08-20") -> int:
    with closing(connect(database_path)) as conn:
        conn.execute("INSERT INTO raw_news (source,collection_method,category,title,url,raw_payload,collected_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", ("test", "rss", category, "제목", url, "{}", "2026-08-20", "now", "now"))
        raw_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        cursor = conn.execute("INSERT INTO clean_news (raw_id,source,category,title,canonical_url,published_at,content,summary,summary_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (raw_id, "test", category, f"{category} 뉴스", url, published_at, content, summary, status, "now", "now"))
        conn.commit()
        return cursor.lastrowid


class AIServicesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "news.db"
        initialize_database(self.path)
        self.ai_config = AIConfig(provider="mock")
        self.provider = MockAIProvider(self.ai_config)

    def tearDown(self): self.temp.cleanup()

    def test_mock_summary_is_persisted(self):
        news_id = seed_clean_news(self.path, content="AI 반도체 시장과 투자 계획에 관한 기사 본문입니다.")
        stats = SummarizerService(self.path, self.ai_config, self.provider).summarize(news_id=news_id, all_news=False, unsummarized=False, limit=None, force=False)
        self.assertEqual(stats.success_count, 1)
        with closing(connect(self.path)) as conn:
            row = conn.execute("SELECT summary_status, key_points, ai_provider FROM clean_news WHERE id=?", (news_id,)).fetchone()
        self.assertEqual(row["summary_status"], "summarized")
        self.assertEqual(row["ai_provider"], "mock")
        self.assertEqual(len(json.loads(row["key_points"])), 2)

    def test_missing_body_is_not_ready_without_provider_call(self):
        news_id = seed_clean_news(self.path, content=None)
        stats = SummarizerService(self.path, self.ai_config, self.provider).summarize(news_id=news_id, all_news=False, unsummarized=False, limit=None, force=False)
        self.assertEqual(stats.skipped_count, 1)
        with closing(connect(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT summary_status FROM clean_news WHERE id=?", (news_id,)).fetchone()[0], "not_ready")

    def test_analysis_is_saved_and_retrievable(self):
        seed_clean_news(self.path, content="본문", status="summarized", summary="IT 산업 변화 요약", category="it", url="https://example.com/it")
        seed_clean_news(self.path, content="본문", status="summarized", summary="경제 정책 변화 요약", category="economy", url="https://example.com/economy")
        service = AnalyzerService(self.path, self.ai_config, AnalysisConfig(minimum_articles=2), self.provider)
        result = service.analyze(date_from="2026-08-01", date_to="2026-08-30", category=None, limit=10)
        self.assertIsNotNone(result)
        self.assertEqual(result.article_count, 2)
        fetched = service.get_result(result.id)
        self.assertIn("Mock", fetched.insights.keywords)

    def test_analysis_balances_categories_present_in_database(self):
        seed_clean_news(self.path, content="본문", status="summarized", summary="첫 요약", category="통신/뉴미디어", url="https://example.com/detail-1")
        seed_clean_news(self.path, content="본문", status="summarized", summary="둘째 요약", category="반도체/디스플레이", url="https://example.com/detail-2")
        service = AnalyzerService(self.path, self.ai_config, AnalysisConfig(minimum_articles=2), self.provider)

        result = service.analyze(date_from=None, date_to=None, category=None, limit=10)

        self.assertIsNotNone(result)
        self.assertEqual(result.article_count, 2)

    def test_date_to_includes_articles_published_later_that_day(self):
        seed_clean_news(self.path, content="본문", status="summarized", summary="첫 번째 요약", category="it", url="https://example.com/late-1", published_at="2026-08-20T12:00:00")
        seed_clean_news(self.path, content="본문", status="summarized", summary="두 번째 요약", category="economy", url="https://example.com/late-2", published_at="2026-08-20T23:59:59")
        result = AnalyzerService(self.path, self.ai_config, AnalysisConfig(minimum_articles=2), self.provider).analyze(date_from="2026-08-20", date_to="2026-08-20", category=None, limit=10)
        self.assertEqual(result.article_count, 2)

    def test_analysis_uses_configured_summary_length_limit(self):
        class CapturingProvider(MockAIProvider):
            def generate_json(self, task, prompt, response_schema, metadata=None):
                self.prompt = prompt
                return super().generate_json(task, prompt, response_schema, metadata)

        seed_clean_news(self.path, content="본문", status="summarized", summary="가" * 20, category="it", url="https://example.com/summary-1")
        seed_clean_news(self.path, content="본문", status="summarized", summary="나" * 20, category="economy", url="https://example.com/summary-2")
        provider = CapturingProvider(self.ai_config)
        AnalyzerService(self.path, self.ai_config, AnalysisConfig(minimum_articles=2, max_summary_chars=10), provider).analyze(date_from=None, date_to=None, category=None, limit=10)
        self.assertIn("가" * 10, provider.prompt)
        self.assertNotIn("가" * 11, provider.prompt)

    def test_analysis_logs_and_reraises_provider_errors(self):
        class FailingProvider(MockAIProvider):
            def generate_json(self, *args, **kwargs):
                raise ProviderTimeoutError("timeout")

        seed_clean_news(self.path, content="본문", status="summarized", summary="첫 번째 요약", category="it", url="https://example.com/error-1")
        seed_clean_news(self.path, content="본문", status="summarized", summary="두 번째 요약", category="economy", url="https://example.com/error-2")
        service = AnalyzerService(self.path, self.ai_config, AnalysisConfig(minimum_articles=2), FailingProvider(self.ai_config))
        with self.assertLogs("news_pipeline.services.analyzer", level="ERROR") as logs:
            with self.assertRaises(ProviderTimeoutError):
                service.analyze(date_from=None, date_to=None, category=None, limit=10)
        self.assertIn("AI 인사이트 생성 실패", "\n".join(logs.output))
