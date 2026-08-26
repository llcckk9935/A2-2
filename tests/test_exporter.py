import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from news_pipeline.cli import _run_export
from news_pipeline.config import load_config
from news_pipeline.database import Database
from news_pipeline.services.exporter import ExporterService


class ExporterServiceIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "data" / "news.db"
        self.database = Database(self.database_path)
        base_config, _ = load_config(Path(__file__).parents[1] / "config.json")
        self.config = base_config.model_copy(
            update={
                "database": base_config.database.model_copy(
                    update={"path": str(self.database_path)}
                ),
                "export": base_config.export.model_copy(
                    update={"output_directory": str(self.root / "exports")}
                ),
            }
        )
        self._seed("it", "2026-08-26T23:59:59", "summarized", 1)
        self._seed("economy", None, "pending", 2)
        self.service = ExporterService()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _seed(self, category, published_at, status, index):
        raw_id = self.database.save_raw_news(
            {
                "source": "test",
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
                "summary": "요약" if status == "summarized" else None,
                "key_points": ["핵심 1", "핵심 2"],
                "summary_status": status,
            }
        )

    def _export(self, **overrides):
        params = {
            "output_format": "csv",
            "status": "all",
            "category": None,
            "date_from": None,
            "date_to": None,
            "output": None,
            "config": self.config,
            "project_root": self.root,
        }
        params.update(overrides)
        return self.service.export(**params)

    def test_csv_export_reads_all_actual_database_rows(self):
        path = self._export(output_format="csv", category="all")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)

    def test_jsonl_preserves_key_points_as_list(self):
        path = self._export(output_format="jsonl", status="summarized")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key_points"], ["핵심 1", "핵심 2"])

    def test_date_to_includes_timestamp_on_same_day_and_skips_missing_date(self):
        path = self._export(
            output_format="jsonl", date_from="2026-08-26", date_to="2026-08-26"
        )
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["title"] for row in rows], ["뉴스 1"])

    def test_xlsx_applies_wrap_text_and_bounded_width(self):
        path = self._export(output_format="xlsx")
        sheet = load_workbook(path).active
        self.assertTrue(sheet["A1"].alignment.wrap_text)
        self.assertTrue(sheet["D2"].alignment.wrap_text)
        self.assertLessEqual(sheet.column_dimensions["D"].width, 50)

    def test_explicit_extension_mismatch_returns_friendly_cli_error(self):
        args = SimpleNamespace(
            format="csv",
            status="all",
            category=None,
            date_from=None,
            date_to=None,
            output="exports/result.xlsx",
        )
        self.assertEqual(_run_export(args, self.config, self.root), 2)

    def test_generated_names_do_not_collide(self):
        first = self._export(output_format="csv")
        second = self._export(output_format="csv")
        self.assertNotEqual(first, second)
