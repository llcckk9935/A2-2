import unittest
import tempfile
from pathlib import Path

from news_pipeline.services.exporter import ExporterService


class ExporterServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ExporterService()
        self.news = self.service._fetch_mock_clean_news()
        
    def test_filter_status_summarized_only(self):
        filtered = self.service._filter_clean_news(
            self.news, status="summarized", category=None, date_from=None, date_to=None
        )
        self.assertTrue(all(n["summary_status"] == "summarized" for n in filtered))

    def test_filter_status_unsummarized_excludes_summarized(self):
        filtered = self.service._filter_clean_news(
            self.news, status="unsummarized", category=None, date_from=None, date_to=None
        )
        self.assertTrue(all(n["summary_status"] != "summarized" for n in filtered))

    def test_filter_by_category(self):
        filtered = self.service._filter_clean_news(
            self.news, status="all", category="it", date_from=None, date_to=None
        )
        self.assertTrue(all(n["category"] == "it" for n in filtered))
        
    def test_filter_by_date_range(self):
        filtered = self.service._filter_clean_news(
            self.news, status="all", category=None,
            date_from="2026-08-21", date_to="2026-08-21",
        )
        self.assertTrue(all(n["published_at"] == "2026-08-21" for n in filtered))

    def test_filter_combined_returns_empty_when_no_match(self):
        filtered = self.service._filter_clean_news(
            self.news, status="summarized", category="economy", date_from=None, date_to=None
        )
        self.assertEqual(filtered, [])
        
    def test_save_csv_uses_utf8_sig_encoding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            self.service._save_csv(self.news, output_path)
            with open(output_path, "rb") as f:
                raw = f.read()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_save_jsonl_produces_valid_json_lines(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.jsonl"
            self.service._save_jsonl(self.news, output_path)
            with open(output_path, encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), len(self.news))
            for line in lines:
                json.loads(line)

    def test_save_xlsx_has_correct_headers(self):
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.xlsx"
            self.service._save_xlsx(self.news, output_path)
            wb = load_workbook(output_path)
            sheet = wb.active
            headers = [cell.value for cell in sheet[1]]
            self.assertEqual(tuple(headers), self.service.EXPORT_COLUMNS)