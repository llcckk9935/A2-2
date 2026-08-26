"""SQLite 연결과 스키마 초기화를 담당한다.

CRUD 함수는 Issue #3에서 이 모듈에 추가한다. 다른 모듈에는 SQL을 작성하지 않는다.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("database")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT,
    collection_method TEXT NOT NULL
        CHECK (collection_method IN ('rss', 'crawl', 'rss+crawl', 'mock')),
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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(analysis_results)")}
        if "excluded_count" not in columns:
            connection.execute("ALTER TABLE analysis_results ADD COLUMN excluded_count INTEGER NOT NULL DEFAULT 0")
        connection.commit()


# =====================================================================
# Issue #3: NewsRepository & CRUD 통합 함수
# =====================================================================

class Database:
    """팀원들의 다양한 호출 방식을 지원하는 DB 관리자 클래스"""
    def __init__(self, database_path: str | Path):
        self.db_path = Path(database_path)
        initialize_database(self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def list_raw_news(
        self,
        *,
        include_cleaned: bool = False,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        """정제 대상을 ID 순서로 조회한다.

        기본값에서는 이미 ``clean_news``에 연결된 raw 항목을 제외한다.
        ``include_cleaned``가 참이면 재정제(upsert) 대상을 포함한다.
        """

        query = "SELECT raw_news.* FROM raw_news"
        params: list[Any] = []
        if not include_cleaned:
            query += " LEFT JOIN clean_news ON clean_news.raw_id = raw_news.id"
            query += " WHERE clean_news.id IS NULL"
        query += " ORDER BY raw_news.id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with closing(self.get_connection()) as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_clean_news_by_raw_id(self, raw_id: int) -> Optional[Dict[str, Any]]:
        """raw 뉴스에 연결된 정제 레코드를 반환한다."""

        with closing(self.get_connection()) as conn:
            row = conn.execute(
                "SELECT * FROM clean_news WHERE raw_id = ?",
                (raw_id,),
            ).fetchone()
            return dict(row) if row else None

    def init_db(self) -> None:
        initialize_database(self.db_path)

    # 1. raw_news 저장
    def save_raw_news(self, data: Dict[str, Any], policy: str = "upsert") -> int:
        now = now_iso()
        collected_at = data.get("collected_at") or now
        payload = data.get("raw_payload", "{}")
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False)

        with closing(self.get_connection()) as conn:
            try:
                if policy == "upsert":
                    conn.execute(
                        """
                        INSERT INTO raw_news (
                            source, source_id, collection_method, category, title, url,
                            published_at_raw, content_raw, raw_payload, collected_at, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            source = excluded.source,
                            source_id = excluded.source_id,
                            collection_method = excluded.collection_method,
                            category = excluded.category,
                            title = excluded.title,
                            published_at_raw = excluded.published_at_raw,
                            content_raw = excluded.content_raw,
                            raw_payload = excluded.raw_payload,
                            updated_at = excluded.updated_at
                        """,
                        (
                            data["source"], data.get("source_id"), data.get("collection_method", "rss"),
                            data.get("category", "General"), data["title"], data["url"],
                            data.get("published_at_raw"), data.get("content_raw"), payload,
                            collected_at, now, now
                        )
                    )
                else:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO raw_news (
                            source, source_id, collection_method, category, title, url,
                            published_at_raw, content_raw, raw_payload, collected_at, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data["source"], data.get("source_id"), data.get("collection_method", "rss"),
                            data.get("category", "General"), data["title"], data["url"],
                            data.get("published_at_raw"), data.get("content_raw"), payload,
                            collected_at, now, now
                        )
                    )
                conn.commit()
                row = conn.execute("SELECT id FROM raw_news WHERE url = ?", (data["url"],)).fetchone()
                return row["id"]
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("raw_news 저장 실패: %s", e)
                raise

    # 2. clean_news 저장
    def save_clean_news(self, data: Dict[str, Any], policy: str = "upsert") -> Optional[int]:
        now = now_iso()
        canonical_url = data["canonical_url"]
        key_points = data.get("key_points", [])
        if isinstance(key_points, list):
            key_points = json.dumps(key_points, ensure_ascii=False)

        with closing(self.get_connection()) as conn:
            try:
                if policy == "upsert":
                    conn.execute(
                        """
                        INSERT INTO clean_news (
                            raw_id, source, category, title, canonical_url, published_at,
                            content, summary, key_points, summary_status, summarized_at,
                            ai_provider, ai_model, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(canonical_url) DO UPDATE SET
                            raw_id = excluded.raw_id,
                            source = excluded.source,
                            category = excluded.category,
                            title = excluded.title,
                            published_at = excluded.published_at,
                            content = excluded.content,
                            summary_status = excluded.summary_status,
                            updated_at = excluded.updated_at
                        """,
                        (
                            data["raw_id"], data["source"], data["category"], data["title"],
                            canonical_url, data.get("published_at"), data.get("content"),
                            data.get("summary"), key_points, data.get("summary_status", "pending"),
                            data.get("summarized_at"), data.get("ai_provider"), data.get("ai_model"),
                            now, now
                        )
                    )
                else:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO clean_news (
                            raw_id, source, category, title, canonical_url, published_at,
                            content, summary, key_points, summary_status, summarized_at,
                            ai_provider, ai_model, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data["raw_id"], data["source"], data["category"], data["title"],
                            canonical_url, data.get("published_at"), data.get("content"),
                            data.get("summary"), key_points, data.get("summary_status", "pending"),
                            data.get("summarized_at"), data.get("ai_provider"), data.get("ai_model"),
                            now, now
                        )
                    )
                conn.commit()
                row = conn.execute("SELECT id FROM clean_news WHERE canonical_url = ?", (canonical_url,)).fetchone()
                return row["id"] if row else None
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("clean_news 저장 실패: %s", e)
                raise

    # 3. 요약 결과 저장
    def save_summary_result(self, clean_news_id: int, result: Dict[str, Any]) -> None:
        now = now_iso()
        key_points = result.get("key_points", [])
        if isinstance(key_points, list):
            key_points = json.dumps(key_points, ensure_ascii=False)

        with closing(self.get_connection()) as conn:
            try:
                conn.execute(
                    """
                    UPDATE clean_news
                    SET summary = ?, key_points = ?, summary_status = 'summarized',
                        summarized_at = ?, ai_provider = ?, ai_model = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        result.get("summary"), key_points, now,
                        result.get("ai_provider"), result.get("ai_model"), now, clean_news_id
                    )
                )
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("요약 결과 저장 실패: %s", e)
                raise

    # 4. 뉴스 조회 함수들
    def get_news_by_id(self, news_id: int) -> Optional[Dict[str, Any]]:
        with closing(self.get_connection()) as conn:
            row = conn.execute("SELECT * FROM clean_news WHERE id = ?", (news_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("key_points"):
                try:
                    res["key_points"] = json.loads(res["key_points"])
                except Exception:
                    pass
            return res

    def get_unsummarized_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        with closing(self.get_connection()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM clean_news
                WHERE summary_status = 'pending' AND content IS NOT NULL AND content != ''
                ORDER BY published_at DESC, id ASC LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def list_news(
        self,
        category: Optional[str] = None,
        summary_status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM clean_news WHERE 1 = 1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if summary_status:
            query += " AND summary_status = ?"
            params.append(summary_status)
        if date_from:
            query += " AND published_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND published_at <= ?"
            params.append(date_to)
        query += " ORDER BY published_at DESC, id DESC LIMIT ?"
        params.append(limit)

        with closing(self.get_connection()) as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("key_points"):
                    try:
                        item["key_points"] = json.loads(item["key_points"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # 5. 분석 결과 저장 및 조회
    def save_analysis_result(self, data: Dict[str, Any]) -> int:
        now = now_iso()
        def dump(val, default):
            v = data.get(val, default)
            return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)

        with closing(self.get_connection()) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO analysis_results (
                        date_from, date_to, category, article_count, trends, keywords,
                        major_issues, common_points, differences, implications,
                        article_ids, category_counts, excluded_count, ai_provider, ai_model, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data.get("date_from"), data.get("date_to"), data.get("category"),
                        data.get("article_count", 0), dump("trends", []), dump("keywords", []),
                        dump("major_issues", []), dump("common_points", []), dump("differences", []),
                        dump("implications", []), dump("article_ids", []), dump("category_counts", {}),
                        data.get("excluded_count", 0), data["ai_provider"], data["ai_model"],
                        data.get("status", "completed"), now
                    )
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("분석 결과 저장 실패: %s", e)
                raise

    def list_analysis_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        with closing(self.get_connection()) as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_results ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_analysis_result(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        with closing(self.get_connection()) as conn:
            row = conn.execute("SELECT * FROM analysis_results WHERE id = ?", (analysis_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            json_cols = ["trends", "keywords", "major_issues", "common_points", "differences", "implications", "article_ids", "category_counts"]
            for c in json_cols:
                if res.get(c):
                    try:
                        res[c] = json.loads(res[c])
                    except Exception:
                        pass
            return res

    # 6. 집계 함수
    def get_category_counts(self) -> Dict[str, int]:
        with closing(self.get_connection()) as conn:
            rows = conn.execute("SELECT category, COUNT(*) AS count FROM clean_news GROUP BY category ORDER BY count DESC").fetchall()
            return {r["category"]: r["count"] for r in rows}

    def get_summary_status_counts(self) -> Dict[str, int]:
        with closing(self.get_connection()) as conn:
            rows = conn.execute("SELECT summary_status, COUNT(*) AS count FROM clean_news GROUP BY summary_status ORDER BY count DESC").fetchall()
            return {r["summary_status"]: r["count"] for r in rows}


# 이전 코드 호환성용 alias
NewsRepository = Database
