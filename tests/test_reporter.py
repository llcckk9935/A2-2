import tempfile
import unittest
from pathlib import Path

from news_pipeline.services.reporter import ReporterService


class ReporterServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ReporterService()
        self.news = self.service._fetch_mock_news()

    def test_count_by_category_aggregates_correctly(self):
        counts = self.service._count_by_category(self.news)
        self.assertEqual(counts, {"it": 1, "economy": 1})

    def test_count_by_date_aggregates_correctly(self):
        counts = self.service._count_by_date(self.news)
        self.assertEqual(counts, {"2026-08-20": 1, "2026-08-21": 1})

    def test_quality_metrics_are_calculated_correctly(self):
        metrics = self.service._calculate_quality_metrics(
            raw_count=3,
            clean_count=2,
            duplicate_count=1,
            summarized_count=2,
        )
        self.assertEqual(metrics["clean_rate"], 0.6667)
        self.assertEqual(metrics["duplicate_rate"], 0.3333)
        self.assertEqual(metrics["summarized_rate"], 1.0)

    def test_quality_metrics_handle_zero_denominator(self):
        metrics = self.service._calculate_quality_metrics(
            raw_count=0,
            clean_count=0,
            duplicate_count=0,
            summarized_count=0,
        )
        self.assertEqual(
            metrics,
            {"clean_rate": 0.0, "duplicate_rate": 0.0, "summarized_rate": 0.0},
        )

    def test_top_n_categories_are_sorted_and_stable(self):
        counts = {"it": 2, "economy": 2, "politics": 1}
        top = self.service._top_n_categories(counts, top_n=2)
        self.assertEqual(top, [("economy", 2), ("it", 2)])

    def test_data_with_no_news_does_not_raise(self):
        counts = self.service._count_by_category([])
        self.assertEqual(counts, {})

        date_counts = self.service._count_by_date([])
        self.assertEqual(date_counts, {})

    def test_missing_insight_is_reported_as_absent(self):
        text = self.service._build_report_text(
            date_from=None,
            date_to=None,
            category=None,
            raw_count=0,
            clean_count=0,
            metrics={"clean_rate": 0.0, "duplicate_rate": 0.0, "summarized_rate": 0.0},
            top_categories=[],
            insight=None,
            chart_paths=[],
        )
        self.assertIn("AI 분석 결과가 없습니다.", text)

    def test_bar_chart_png_is_created(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "bar.png"
            self.service._setup_korean_font()
            counts = self.service._count_by_category(self.news)

            result_path = self.service._draw_category_bar_chart(counts, output_path)

            self.assertTrue(result_path.exists())

    def test_report_file_is_created(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            saved_path = self.service._save_report_file(
                "테스트 리포트", output_dir, "md"
            )

            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_text(encoding="utf-8"), "테스트 리포트")