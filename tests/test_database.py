import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from news_pipeline.database import connect, initialize_database


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
