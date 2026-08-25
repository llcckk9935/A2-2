"""Issue #11 스키마 제약 검증.

CRUD 구현(Issue #3)과 무관하게, 스키마 자체가 잘못된 데이터를 거부하는지 확인한다.
정제 단계의 중복 정책과 필수 필드 검증이 기댈 수 있는 최소 보장을 여기서 고정한다.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from news_pipeline.database import connect, initialize_database


TIMESTAMP = "2026-08-26T09:00:00+09:00"

RAW_DEFAULTS = {
    "source": "inews24",
    "collection_method": "rss",
    "category": "it",
    "title": "테스트 기사",
    "url": "https://www.inews24.com/view/1",
    "collected_at": TIMESTAMP,
    "created_at": TIMESTAMP,
    "updated_at": TIMESTAMP,
}

CLEAN_DEFAULTS = {
    "raw_id": None,
    "source": "inews24",
    "category": "it",
    "title": "테스트 기사",
    "canonical_url": "https://www.inews24.com/view/1",
    "created_at": TIMESTAMP,
    "updated_at": TIMESTAMP,
}


def build_insert(table: str, values: dict) -> tuple[str, tuple]:
    """컬럼 이름을 값에서 직접 만들어, 추가 컬럼도 INSERT문에 반영되게 한다."""

    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    return statement, tuple(values[column] for column in columns)


class SchemaTestCase(unittest.TestCase):
    """임시 DB에 스키마를 만들고 제약 조건을 검증한다."""

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self._temporary_directory.name) / "schema_test.db"
        initialize_database(self.database_path)
        self.connection = connect(self.database_path)

    def tearDown(self) -> None:
        self.connection.close()
        self._temporary_directory.cleanup()

    def insert_raw(self, url: str = "https://www.inews24.com/view/1", **overrides) -> int:
        values = {**RAW_DEFAULTS, "url": url, **overrides}
        cursor = self.connection.execute(*build_insert("raw_news", values))
        return int(cursor.lastrowid)

    def insert_clean(self, raw_id: int, canonical_url: str = "https://www.inews24.com/view/1", **overrides) -> int:
        values = {
            **CLEAN_DEFAULTS,
            "raw_id": raw_id,
            "canonical_url": canonical_url,
            **overrides,
        }
        cursor = self.connection.execute(*build_insert("clean_news", values))
        return int(cursor.lastrowid)


class RawNewsConstraintTestCase(SchemaTestCase):
    def test_duplicate_url_is_rejected(self):
        """중복 뉴스: 같은 URL은 두 번 저장되지 않는다."""

        self.insert_raw()

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_raw()

    def test_different_urls_are_accepted(self):
        self.insert_raw("https://www.inews24.com/view/1")
        self.insert_raw("https://www.inews24.com/view/2")

        count = self.connection.execute("SELECT COUNT(*) FROM raw_news").fetchone()[0]
        self.assertEqual(count, 2)

    def test_unknown_collection_method_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_raw(collection_method="selenium")

    def test_supported_collection_methods_are_accepted(self):
        for index, method in enumerate(("rss", "crawl", "rss+crawl")):
            with self.subTest(method=method):
                self.insert_raw(
                    f"https://www.inews24.com/view/m{index}",
                    collection_method=method,
                )

    def test_required_fields_reject_null(self):
        """필수 필드 누락: NOT NULL 컬럼은 비어 있을 수 없다."""

        for column in ("source", "collection_method", "category", "title", "url", "collected_at"):
            with self.subTest(column=column):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.insert_raw(**{column: None})

    def test_raw_payload_defaults_to_empty_object(self):
        raw_id = self.insert_raw()

        row = self.connection.execute(
            "SELECT raw_payload FROM raw_news WHERE id = ?", (raw_id,)
        ).fetchone()

        self.assertEqual(row["raw_payload"], "{}")


class CleanNewsConstraintTestCase(SchemaTestCase):
    def test_duplicate_canonical_url_is_rejected(self):
        first = self.insert_raw("https://www.inews24.com/view/1")
        second = self.insert_raw("https://www.inews24.com/view/2")
        self.insert_clean(first, "https://www.inews24.com/view/1")

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_clean(second, "https://www.inews24.com/view/1")

    def test_one_clean_row_per_raw_row(self):
        raw_id = self.insert_raw()
        self.insert_clean(raw_id, "https://www.inews24.com/view/1")

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_clean(raw_id, "https://www.inews24.com/view/2")

    def test_unknown_raw_id_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_clean(9999)

    def test_summary_status_defaults_to_pending(self):
        raw_id = self.insert_raw()
        clean_id = self.insert_clean(raw_id)

        row = self.connection.execute(
            "SELECT summary_status, key_points FROM clean_news WHERE id = ?", (clean_id,)
        ).fetchone()

        self.assertEqual(row["summary_status"], "pending")
        self.assertEqual(row["key_points"], "[]")

    def test_unknown_summary_status_is_rejected(self):
        raw_id = self.insert_raw()

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_clean(raw_id, summary_status="done")

    def test_supported_summary_statuses_are_accepted(self):
        for index, status in enumerate(("pending", "summarized", "failed", "not_ready")):
            with self.subTest(status=status):
                raw_id = self.insert_raw(f"https://www.inews24.com/view/s{index}")
                self.insert_clean(
                    raw_id,
                    f"https://www.inews24.com/view/s{index}",
                    summary_status=status,
                )

    def test_deleting_raw_news_cascades_to_clean_news(self):
        """PRAGMA foreign_keys가 실제로 켜져 있어야 CASCADE가 동작한다."""

        raw_id = self.insert_raw()
        self.insert_clean(raw_id)

        self.connection.execute("DELETE FROM raw_news WHERE id = ?", (raw_id,))

        count = self.connection.execute("SELECT COUNT(*) FROM clean_news").fetchone()[0]
        self.assertEqual(count, 0)


class CollectionRunConstraintTestCase(SchemaTestCase):
    def insert_run(self, status: str) -> None:
        self.connection.execute(
            "INSERT INTO collection_runs "
            "(source, collection_method, started_at, status) VALUES (?, ?, ?, ?)",
            ("inews24", "rss", TIMESTAMP, status),
        )

    def test_supported_statuses_are_accepted(self):
        for status in ("running", "completed", "partial", "failed"):
            with self.subTest(status=status):
                self.insert_run(status)

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_run("cancelled")


class SchemaShapeTestCase(SchemaTestCase):
    def test_initialize_database_is_idempotent(self):
        """같은 명령을 다시 실행해도 스키마가 깨지지 않는다."""

        self.insert_raw()
        self.connection.commit()

        initialize_database(self.database_path)

        with closing(connect(self.database_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM raw_news").fetchone()[0]

        self.assertEqual(count, 1)

    def test_expected_indexes_exist(self):
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
        index_names = {row["name"] for row in rows}

        self.assertTrue(
            {
                "idx_raw_news_category",
                "idx_clean_news_summary_status",
                "idx_analysis_results_created_at",
            }
            <= index_names
        )
