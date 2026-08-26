from pathlib import Path
import sqlite3
import json
import logging


logging.basicConfig(level=logging.ERROR)


class NewsRepository:
    def __init__(self, db_path="ai_news_storage_v1.db"):
        self.db_path = Path(db_path).resolve()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        conn = self._connect()

        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT,
                collection_method TEXT NOT NULL,
                category TEXT,
                title TEXT,
                url TEXT UNIQUE,
                published_at_raw TEXT,
                content_raw TEXT,
                raw_payload TEXT,
                collected_at TEXT NOT NULL DEFAULT (datetime('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS clean_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER,
                source TEXT,
                category TEXT,
                title TEXT,
                canonical_url TEXT UNIQUE,
                published_at TEXT,
                content TEXT,
                summary TEXT,
                key_points TEXT,
                summary_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (summary_status IN ('pending', 'summarized', 'failed', 'not_ready')),
                summarized_at TEXT,
                ai_provider TEXT,
                ai_model TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (raw_id) REFERENCES raw_news(id)
            );

            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_from TEXT,
                date_to TEXT,
                category TEXT,
                article_count INTEGER NOT NULL DEFAULT 0,
                trends TEXT,
                keywords TEXT,
                major_issues TEXT,
                common_points TEXT,
                differences TEXT,
                implications TEXT,
                article_ids TEXT,
                category_counts TEXT,
                ai_provider TEXT,
                ai_model TEXT,
                status TEXT NOT NULL DEFAULT 'success'
                    CHECK (status IN ('success', 'failed', 'pending')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                collection_method TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                requested_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                duplicate_count INTEGER DEFAULT 0,
                status TEXT NOT NULL
                    CHECK (status IN ('running', 'success', 'failed', 'partial')),
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_raw_news_url
            ON raw_news(url);

            CREATE INDEX IF NOT EXISTS idx_clean_news_status
            ON clean_news(summary_status);

            CREATE INDEX IF NOT EXISTS idx_clean_news_category
            ON clean_news(category);

            CREATE INDEX IF NOT EXISTS idx_clean_news_published_at
            ON clean_news(published_at);

            CREATE INDEX IF NOT EXISTS idx_analysis_results_created_at
            ON analysis_results(created_at);

            CREATE INDEX IF NOT EXISTS idx_collection_runs_started_at
            ON collection_runs(started_at);
            """)

            conn.commit()

        except sqlite3.Error:
            conn.rollback()
            logging.error("DB 초기화 실패", exc_info=True)
            raise

        finally:
            conn.close()

    def save_raw_news(self, data, policy="skip"):
        """
        raw 뉴스 저장
        policy:
        - skip: 같은 url이 있으면 기존 데이터 유지
        - upsert: 같은 url이 있으면 기존 데이터 업데이트
        """
        conn = self._connect()

        try:
            if policy == "skip":
                conn.execute("""
                INSERT OR IGNORE INTO raw_news (
                    source,
                    source_id,
                    collection_method,
                    category,
                    title,
                    url,
                    published_at_raw,
                    content_raw,
                    raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("source"),
                    data.get("source_id"),
                    data.get("collection_method"),
                    data.get("category"),
                    data.get("title"),
                    data.get("url"),
                    data.get("published_at_raw"),
                    data.get("content_raw"),
                    json.dumps(data.get("raw_payload"), ensure_ascii=False)
                    if isinstance(data.get("raw_payload"), (dict, list))
                    else data.get("raw_payload")
                ))

            elif policy == "upsert":
                conn.execute("""
                INSERT INTO raw_news (
                    source,
                    source_id,
                    collection_method,
                    category,
                    title,
                    url,
                    published_at_raw,
                    content_raw,
                    raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url)
                DO UPDATE SET
                    source = excluded.source,
                    source_id = excluded.source_id,
                    collection_method = excluded.collection_method,
                    category = excluded.category,
                    title = excluded.title,
                    published_at_raw = excluded.published_at_raw,
                    content_raw = excluded.content_raw,
                    raw_payload = excluded.raw_payload,
                    updated_at = datetime('now')
                """, (
                    data.get("source"),
                    data.get("source_id"),
                    data.get("collection_method"),
                    data.get("category"),
                    data.get("title"),
                    data.get("url"),
                    data.get("published_at_raw"),
                    data.get("content_raw"),
                    json.dumps(data.get("raw_payload"), ensure_ascii=False)
                    if isinstance(data.get("raw_payload"), (dict, list))
                    else data.get("raw_payload")
                ))

            else:
                raise ValueError("policy는 'skip' 또는 'upsert'만 가능합니다.")

            conn.commit()

            row = conn.execute(
                "SELECT id FROM raw_news WHERE url = ?",
                (data.get("url"),)
            ).fetchone()

            return row["id"] if row else None

        except sqlite3.Error:
            conn.rollback()
            logging.error("raw_news 저장 실패", exc_info=True)
            raise

        finally:
            conn.close()

    def save_clean_news(self, data, policy="skip"):
        """
        clean 뉴스 저장
        canonical_url 기준으로 중복 처리
        """
        conn = self._connect()

        try:
            if policy == "skip":
                conn.execute("""
                INSERT OR IGNORE INTO clean_news (
                    raw_id,
                    source,
                    category,
                    title,
                    canonical_url,
                    published_at,
                    content,
                    summary_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("raw_id"),
                    data.get("source"),
                    data.get("category"),
                    data.get("title"),
                    data.get("canonical_url"),
                    data.get("published_at"),
                    data.get("content"),
                    data.get("summary_status", "pending")
                ))

            elif policy == "upsert":
                conn.execute("""
                INSERT INTO clean_news (
                    raw_id,
                    source,
                    category,
                    title,
                    canonical_url,
                    published_at,
                    content,
                    summary_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_url)
                DO UPDATE SET
                    raw_id = excluded.raw_id,
                    source = excluded.source,
                    category = excluded.category,
                    title = excluded.title,
                    published_at = excluded.published_at,
                    content = excluded.content,
                    updated_at = datetime('now')
                """, (
                    data.get("raw_id"),
                    data.get("source"),
                    data.get("category"),
                    data.get("title"),
                    data.get("canonical_url"),
                    data.get("published_at"),
                    data.get("content"),
                    data.get("summary_status", "pending")
                ))

            else:
                raise ValueError("policy는 'skip' 또는 'upsert'만 가능합니다.")

            conn.commit()

            row = conn.execute(
                "SELECT id FROM clean_news WHERE canonical_url = ?",
                (data.get("canonical_url"),)
            ).fetchone()

            return row["id"] if row else None

        except sqlite3.Error:
            conn.rollback()
            logging.error("clean_news 저장 실패", exc_info=True)
            raise

        finally:
            conn.close()

    def get_news_by_id(self, news_id):
        conn = self._connect()

        try:
            row = conn.execute("""
            SELECT *
            FROM clean_news
            WHERE id = ?
            """, (news_id,)).fetchone()

            if row is None:
                return None

            news = dict(row)

            if news.get("key_points"):
                news["key_points"] = json.loads(news["key_points"])

            return news

        finally:
            conn.close()

    def get_unsummarized_news(self, limit=10):
        conn = self._connect()

        try:
            rows = conn.execute("""
            SELECT *
            FROM clean_news
            WHERE summary_status = 'pending'
            ORDER BY published_at DESC
            LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    def save_summary_result(self, clean_news_id, result):
        """
        AI 요약 결과 저장

        result 예시:
        {
            "summary": "요약문",
            "key_points": ["핵심1", "핵심2"],
            "ai_provider": "gemini",
            "ai_model": "gemini-1.5-flash"
        }
        """
        conn = self._connect()

        try:
            conn.execute("""
            UPDATE clean_news
            SET
                summary = ?,
                key_points = ?,
                summary_status = 'summarized',
                summarized_at = datetime('now'),
                ai_provider = ?,
                ai_model = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """, (
                result.get("summary"),
                json.dumps(result.get("key_points", []), ensure_ascii=False),
                result.get("ai_provider"),
                result.get("ai_model"),
                clean_news_id
            ))

            conn.commit()

        except sqlite3.Error:
            conn.rollback()
            logging.error("요약 결과 저장 실패", exc_info=True)
            raise

        finally:
            conn.close()

    def save_analysis_result(self, data):
        """
        AI 종합 분석 결과 저장
        목록/객체 데이터는 JSON 문자열로 저장
        """
        conn = self._connect()

        try:
            cursor = conn.execute("""
            INSERT INTO analysis_results (
                date_from,
                date_to,
                category,
                article_count,
                trends,
                keywords,
                major_issues,
                common_points,
                differences,
                implications,
                article_ids,
                category_counts,
                ai_provider,
                ai_model,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("date_from"),
                data.get("date_to"),
                data.get("category"),
                data.get("article_count", 0),
                json.dumps(data.get("trends", []), ensure_ascii=False),
                json.dumps(data.get("keywords", []), ensure_ascii=False),
                json.dumps(data.get("major_issues", []), ensure_ascii=False),
                json.dumps(data.get("common_points", []), ensure_ascii=False),
                json.dumps(data.get("differences", []), ensure_ascii=False),
                json.dumps(data.get("implications", []), ensure_ascii=False),
                json.dumps(data.get("article_ids", []), ensure_ascii=False),
                json.dumps(data.get("category_counts", {}), ensure_ascii=False),
                data.get("ai_provider"),
                data.get("ai_model"),
                data.get("status", "success")
            ))

            conn.commit()
            return cursor.lastrowid

        except sqlite3.Error:
            conn.rollback()
            logging.error("분석 결과 저장 실패", exc_info=True)
            raise

        finally:
            conn.close()

    def list_analysis_results(self, limit=20):
        conn = self._connect()

        try:
            rows = conn.execute(
                "SELECT id, date_from, date_to, category, article_count, "
                "ai_provider, ai_model, status, created_at "
                "FROM analysis_results "
                "ORDER BY created_at DESC, id DESC "
                "LIMIT ?",
                (limit,)
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    def get_analysis_result(self, analysis_id):
        conn = self._connect()

        try:
            row = conn.execute(
                "SELECT * FROM analysis_results WHERE id = ?",
                (analysis_id,)
            ).fetchone()

            if row is None:
                return None

            result = dict(row)

            json_fields = [
                "trends",
                "keywords",
                "major_issues",
                "common_points",
                "differences",
                "implications",
                "article_ids",
                "category_counts",
            ]

            for field in json_fields:
                if result.get(field):
                    result[field] = json.loads(result[field])

            return result

        finally:
            conn.close()

    def list_news(
        self,
        category=None,
        summary_status=None,
        date_from=None,
        date_to=None,
        limit=50
    ):
        conn = self._connect()

        try:
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

            rows = conn.execute(query, params).fetchall()

            result = []

            for row in rows:
                news = dict(row)

                if news.get("key_points"):
                    news["key_points"] = json.loads(news["key_points"])

                result.append(news)

            return result

        finally:
            conn.close()

    def get_category_counts(self):
        conn = self._connect()

        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) AS count "
                "FROM clean_news "
                "GROUP BY category "
                "ORDER BY count DESC"
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    def get_summary_status_counts(self):
        conn = self._connect()

        try:
            rows = conn.execute(
                "SELECT summary_status, COUNT(*) AS count "
                "FROM clean_news "
                "GROUP BY summary_status "
                "ORDER BY count DESC"
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    def save_collection_run(self, data):
        conn = self._connect()

        try:
            cursor = conn.execute(
                "INSERT INTO collection_runs ("
                "source, collection_method, started_at, finished_at, "
                "requested_count, success_count, failure_count, "
                "duplicate_count, status, error_message"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data.get("source"),
                    data.get("collection_method"),
                    data.get("started_at"),
                    data.get("finished_at"),
                    data.get("requested_count", 0),
                    data.get("success_count", 0),
                    data.get("failure_count", 0),
                    data.get("duplicate_count", 0),
                    data.get("status"),
                    data.get("error_message"),
                )
            )

            conn.commit()
            return cursor.lastrowid

        except sqlite3.Error:
            conn.rollback()
            logging.error("수집 실행 기록 저장 실패", exc_info=True)
            raise

        finally:
            conn.close()
