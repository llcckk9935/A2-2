import tempfile
import unittest
from pathlib import Path

from news_pipeline.database import Database
from news_pipeline.services.reporter import ReporterService


class ReporterServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "news.db")
        for index, (category, published_at) in enumerate(
            (("it", "2026-08-20"), ("economy", "2026-08-21")), start=1
        ):
            raw_id = self.database.save_raw_news(
                {
                    "source": "test",
                    "source_id": str(index),
                    "collection_method": "crawl",
                    "category": category,
                    "title": f"뉴스 {index}",
                    "url": f"https://example.com/{index}",
                    "published_at_raw": published_at,
                    "content_raw": "본문",
                }
            )
            self.database.save_clean_news(
                {
                    "raw_id": raw_id,
                    "source": "test",
                    "category": category,
                    "title": f"뉴스 {index}",
                    "canonical_url": f"https://example.com/{index}",
                    "published_at": published_at,
                    "content": "본문",
                    "summary": "요약",
                    "summary_status": "summarized",
                }
            )
        self.database.save_analysis_result(
            {
                "article_count": 2,
                "trends": ["실제 저장 트렌드"],
                "keywords": ["AI", "경제"],
                "major_issues": ["주요 이슈"],
                "common_points": ["공통점"],
                "differences": ["차이점"],
                "implications": ["시사점"],
                "article_ids": [1, 2],
                "category_counts": {"it": 1, "economy": 1},
                "ai_provider": "mock",
                "ai_model": "mock-model",
            }
        )
        self.service = ReporterService(
            self.root / "news.db", output_directory=self.root / "reports"
        )
        self.news = self.database.list_news(limit=None)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_count_by_category_aggregates_correctly(self):
        self.assertEqual(
            self.service._count_by_category(self.news), {"it": 1, "economy": 1}
        )

    def test_count_by_date_aggregates_correctly(self):
        self.assertEqual(
            self.service._count_by_date(self.news),
            {"2026-08-20": 1, "2026-08-21": 1},
        )

    def test_count_by_date_ignores_missing_dates(self):
        self.assertEqual(self.service._count_by_date([{"published_at": None}]), {})

    def test_quality_metrics_are_calculated_correctly(self):
        metrics = self.service._calculate_quality_metrics(
            raw_count=3,
            clean_count=2,
            duplicate_count=1,
            summarized_count=2,
            required_complete_count=2,
            content_count=1,
        )
        self.assertEqual(metrics["clean_rate"], 0.6667)
        self.assertEqual(metrics["duplicate_rate"], 0.3333)
        self.assertEqual(metrics["summarized_rate"], 1.0)
        self.assertEqual(metrics["required_field_rate"], 1.0)
        self.assertEqual(metrics["content_rate"], 0.5)

    def test_quality_metrics_handle_zero_denominator(self):
        metrics = self.service._calculate_quality_metrics(
            raw_count=0, clean_count=0, duplicate_count=0, summarized_count=0
        )
        self.assertEqual(
            metrics,
            {
                "clean_rate": 0.0,
                "duplicate_rate": 0.0,
                "summarized_rate": 0.0,
                "required_field_rate": 0.0,
                "content_rate": 0.0,
            },
        )

    def test_top_n_categories_are_sorted_and_stable(self):
        counts = {"it": 2, "economy": 2, "politics": 1}
        self.assertEqual(
            self.service._top_n_categories(counts, top_n=2),
            [("economy", 2), ("it", 2)],
        )

    def test_missing_insight_is_reported_as_absent(self):
        text = self.service._build_report_text(
            date_from=None,
            date_to=None,
            category=None,
            raw_count=0,
            clean_count=0,
            metrics={
                "clean_rate": 0.0,
                "duplicate_rate": 0.0,
                "summarized_rate": 0.0,
                "required_field_rate": 0.0,
                "content_rate": 0.0,
            },
            top_categories=[],
            insight=None,
            chart_paths=[],
        )
        self.assertIn("AI 분석 결과가 없습니다.", text)

    def test_generate_reads_database_and_creates_report_and_charts(self):
        paths = self.service.generate(
            date_from=None,
            date_to=None,
            category=None,
            top_n=5,
            output_format="md",
            output=None,
        )

        self.assertEqual(len(paths), 3)
        self.assertTrue(all(path.exists() for path in paths))
        report = paths[-1].read_text(encoding="utf-8")
        self.assertIn("raw 뉴스 수: 2", report)
        self.assertIn("clean 뉴스 수: 2", report)
        self.assertIn("실제 저장 트렌드", report)

    def test_report_file_uses_unique_name(self):
        first = self.service._save_report_file("첫 번째", self.root, "md")
        second = self.service._save_report_file("두 번째", self.root, "md")
        self.assertNotEqual(first, second)
