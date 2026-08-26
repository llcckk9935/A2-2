import unittest
import tempfile
import json
import csv
from contextlib import closing
from pathlib import Path

from news_pipeline.services.exporter import ExporterService


def _make_test_db(db_path, rows):
    """임시 SQLite DB를 만들고 clean_news에 테스트 데이터를 넣는다."""
    from news_pipeline.database import Database

    db = Database(str(db_path))
    with closing(db.get_connection()) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for row in rows:
            conn.execute(
                """
                INSERT INTO clean_news (
                    raw_id, source, category, title, canonical_url, published_at,
                    content, summary, key_points, summary_status, summarized_at,
                    ai_provider, ai_model, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["raw_id"], row["source"], row["category"], row["title"],
                    row["canonical_url"], row.get("published_at"), row.get("content"),
                    row.get("summary"), row.get("key_points", "[]"),
                    row.get("summary_status", "pending"), row.get("summarized_at"),
                    row.get("ai_provider"), row.get("ai_model"),
                    row.get("created_at", "2026-08-26T00:00:00"),
                    row.get("updated_at", "2026-08-26T00:00:00"),
                )
            )
        conn.commit()
    return db_path

class ExporterServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ExporterService()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test.db"
        _make_test_db(
            self.db_path,
            rows=[
                {
                    "raw_id": 1,
                    "source": "inews24",
                    "category": "it",
                    "title": "AI 반도체 시장 급성장",
                    "canonical_url": "https://example.com/1",
                    "published_at": "2026-08-20",
                    "summary": "AI 반도체 수요가 늘고 있다.",
                    "key_points": '["수요 증가", "가격 상승"]',
                    "summary_status": "summarized",
                    "summarized_at": "2026-08-20T10:00:00",
                },
                {
                    "raw_id": 2,
                    "source": "inews24",
                    "category": "economy",
                    "title": "금리 동결 발표",
                    "canonical_url": "https://example.com/2",
                    "published_at": "2026-08-21",
                    "summary_status": "pending",
                },
            ],
        )

        from news_pipeline.database import Database
        db = Database(str(self.db_path))
        rows = db.list_news(limit=1_000_000)
        for row in rows:
            key_points = row.get("key_points")
            if isinstance(key_points, str):
                try:
                    row["key_points"] = json.loads(key_points)
                except (json.JSONDecodeError, TypeError):
                    row["key_points"] = []
        self.news = [
            {col: row.get(col) for col in self.service.EXPORT_COLUMNS} for row in rows
        ]

    def tearDown(self):
        self.tmp_dir.cleanup()
        
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

    def test_save_csv_handles_commas_and_newlines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "comma_test.db"
            _make_test_db(
                db_path,
                rows=[
                    {
                        "raw_id": 99,
                        "source": "inews24",
                        "category": "it",
                        "title": "쉼표, 줄바꿈\n테스트 제목",
                        "canonical_url": "https://example.com/99",
                        "published_at": "2026-08-22",
                        "summary": "요약에, 쉼표와\n줄바꿈이 포함된 경우",
                        "key_points": '["포인트 A, B", "줄바꿈\\n포함"]',
                        "summary_status": "summarized",
                    },
                ],
            )
            from news_pipeline.database import Database
            db = Database(str(db_path))
            rows = db.list_news(limit=10)
            for row in rows:
                key_points = row.get("key_points")
                if isinstance(key_points, str):
                    row["key_points"] = json.loads(key_points)
            news = [
                {col: row.get(col) for col in self.service.EXPORT_COLUMNS} for row in rows
            ]

            output_path = Path(tmpdir) / "comma_test.csv"
            self.service._save_csv(news, output_path)

            with open(output_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                result_rows = list(reader)

            self.assertEqual(len(result_rows), 1)
            self.assertEqual(result_rows[0]["title"], "쉼표, 줄바꿈\n테스트 제목")
            self.assertEqual(
                result_rows[0]["summary"], "요약에, 쉼표와\n줄바꿈이 포함된 경우"
            )