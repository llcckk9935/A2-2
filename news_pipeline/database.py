"""SQLite 연결과 스키마 초기화를 담당한다.

CRUD 함수는 Issue #3에서 이 모듈에 추가한다. 다른 모듈에는 SQL을 작성하지 않는다.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT,
    collection_method TEXT NOT NULL
        CHECK (collection_method IN ('rss', 'crawl', 'rss+crawl')),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at_raw TEXT,
    content_raw TEXT,
    raw_payload TEXT NOT NULL DEFAULT '{}',
    collected_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clean_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL UNIQUE,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    published_at TEXT,
    content TEXT,
    summary TEXT,
    key_points TEXT NOT NULL DEFAULT '[]',
    summary_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (summary_status IN ('pending', 'summarized', 'failed', 'not_ready')),
    summary_error TEXT,
    summarized_at TEXT,
    ai_provider TEXT,
    ai_model TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (raw_id) REFERENCES raw_news(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_from TEXT,
    date_to TEXT,
    category TEXT,
    article_count INTEGER NOT NULL,
    trends TEXT NOT NULL DEFAULT '[]',
    keywords TEXT NOT NULL DEFAULT '[]',
    major_issues TEXT NOT NULL DEFAULT '[]',
    common_points TEXT NOT NULL DEFAULT '[]',
    differences TEXT NOT NULL DEFAULT '[]',
    implications TEXT NOT NULL DEFAULT '[]',
    article_ids TEXT NOT NULL DEFAULT '[]',
    category_counts TEXT NOT NULL DEFAULT '{}',
    excluded_count INTEGER NOT NULL DEFAULT 0,
    ai_provider TEXT NOT NULL,
    ai_model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    collection_method TEXT NOT NULL,
    category TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    requested_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
        CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_news_category ON raw_news(category);
CREATE INDEX IF NOT EXISTS idx_raw_news_collected_at ON raw_news(collected_at);
CREATE INDEX IF NOT EXISTS idx_clean_news_category ON clean_news(category);
CREATE INDEX IF NOT EXISTS idx_clean_news_published_at ON clean_news(published_at);
CREATE INDEX IF NOT EXISTS idx_clean_news_summary_status ON clean_news(summary_status);
CREATE INDEX IF NOT EXISTS idx_analysis_results_created_at ON analysis_results(created_at);
"""


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    with closing(connect(database_path)) as connection:
        connection.executescript(SCHEMA_SQL)
        # 기존 개발 DB도 Issue #8 필드를 사용할 수 있도록 가벼운 마이그레이션을 수행한다.
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(analysis_results)")}
        if "excluded_count" not in columns:
            connection.execute("ALTER TABLE analysis_results ADD COLUMN excluded_count INTEGER NOT NULL DEFAULT 0")
        connection.commit()
