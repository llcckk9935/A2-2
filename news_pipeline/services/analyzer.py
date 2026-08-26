"""저장된 뉴스 요약을 종합해 인사이트를 생성하고 조회한다."""

from __future__ import annotations

import json
import logging
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from news_pipeline.config import AIConfig, AnalysisConfig
from news_pipeline.database import connect
from news_pipeline.models import AnalysisResult, InsightResult
from news_pipeline.providers.base import AIProvider, AIProviderError


class AnalyzerService:
    def __init__(self, database_path: Path, ai_config: AIConfig, analysis_config: AnalysisConfig, provider: AIProvider):
        self.database_path, self.ai_config, self.analysis_config, self.provider = database_path, ai_config, analysis_config, provider
        self.logger = logging.getLogger(__name__)

    def analyze(self, *, date_from: str | None, date_to: str | None, category: str | None, limit: int | None) -> AnalysisResult | None:
        rows = self._select_articles(date_from, date_to, category)
        requested = min(limit or self.analysis_config.max_articles, self.analysis_config.max_articles)
        rows, excluded_count = self._limit_balanced(rows, requested, category)
        if len(rows) < self.analysis_config.minimum_articles:
            self.logger.warning("분석 데이터 부족: %s건 (최소 %s건)", len(rows), self.analysis_config.minimum_articles)
            return None
        category_counts = dict(Counter(row["category"] for row in rows))
        self.logger.info("분석 대상 %s건, 카테고리별=%s", len(rows), category_counts)
        prompt = _analysis_prompt(
            rows,
            category_counts,
            self.analysis_config.max_summary_chars,
        )
        try:
            data = self.provider.generate_json(
                "analysis", prompt, InsightResult,
                {"category": category or "all", "article_count": len(rows)},
            )
            insights = _validate_insights(data)
        except AIProviderError as exc:
            self.logger.error("AI 인사이트 생성 실패: %s", exc)
            raise
        result = AnalysisResult(date_from, date_to, category, len(rows), insights, [row["id"] for row in rows], category_counts, self.provider.provider_name, self.provider.model_name)
        with closing(connect(self.database_path)) as connection:
            cursor = connection.execute(
                """INSERT INTO analysis_results (date_from,date_to,category,article_count,trends,keywords,major_issues,common_points,differences,implications,article_ids,category_counts,excluded_count,ai_provider,ai_model,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (date_from, date_to, category, result.article_count, *[json.dumps(getattr(insights, key), ensure_ascii=False) for key in ("trends", "keywords", "major_issues", "common_points", "differences", "implications")], json.dumps(result.article_ids), json.dumps(category_counts), excluded_count, result.ai_provider, result.ai_model, "completed", _now()),
            )
            connection.commit()
            result.id = cursor.lastrowid
        self.logger.info("분석 저장 완료: analysis_id=%s", result.id)
        return result

    def list_results(self) -> list[AnalysisResult]:
        with closing(connect(self.database_path)) as connection:
            rows = connection.execute("SELECT * FROM analysis_results ORDER BY id DESC").fetchall()
        return [_row_to_result(row) for row in rows]

    def get_result(self, result_id: int) -> AnalysisResult | None:
        with closing(connect(self.database_path)) as connection:
            row = connection.execute("SELECT * FROM analysis_results WHERE id=?", (result_id,)).fetchone()
        return _row_to_result(row) if row else None

    def _select_articles(self, date_from, date_to, category):
        clauses, params = ["summary_status='summarized'", "summary IS NOT NULL", "TRIM(summary) != ''"], []
        if date_from: clauses.append("published_at >= ?"); params.append(date_from)
        if date_to: clauses.append("published_at < ?"); params.append((date.fromisoformat(date_to) + timedelta(days=1)).isoformat())
        if category and category != "all": clauses.append("category = ?"); params.append(category)
        sql = "SELECT * FROM clean_news WHERE " + " AND ".join(clauses) + " ORDER BY published_at, id"
        with closing(connect(self.database_path)) as connection:
            rows = connection.execute(sql, params).fetchall()
        unique, seen = [], set()
        for row in rows:
            if row["canonical_url"] not in seen:
                seen.add(row["canonical_url"]); unique.append(row)
        return unique

    def _limit_balanced(self, rows, requested: int, category: str | None):
        if category or not self.analysis_config.balance_categories:
            return rows[:requested], max(0, len(rows) - requested)
        category_names = sorted({row["category"] for row in rows})
        buckets = {name: [r for r in rows if r["category"] == name] for name in category_names}
        selected = []
        while len(selected) < requested and any(buckets.values()):
            for name in buckets:
                if buckets[name] and len(selected) < requested:
                    selected.append(buckets[name].pop(0))
        return selected, max(0, len(rows) - len(selected))


def _now() -> str: return datetime.now(timezone.utc).isoformat()


def _analysis_prompt(rows, category_counts, max_summary_chars: int) -> str:
    articles = "\n".join(
        f"[{row['category']}] {row['title']}\n요약: {row['summary'][:max_summary_chars]}"
        for row in rows
    )
    return f"""제공된 뉴스 제목과 요약문만 근거로 한국어 뉴스 인사이트를 JSON으로 작성하세요. 외부 사실과 편향된 평가는 추가하지 마세요.
각 카테고리의 기사 수: {json.dumps(category_counts, ensure_ascii=False)}
데이터가 부족하면 그 사실을 명시하세요. trends, keywords, major_issues, common_points, differences, implications는 모두 중복 없는 문자열 목록이어야 합니다.
기사:\n{articles}"""


def _validate_insights(data: dict) -> InsightResult:
    result = InsightResult.model_validate(data)
    cleaned = {key: list(dict.fromkeys(item.strip() for item in getattr(result, key) if item.strip())) for key in InsightResult.model_fields}
    if any(not values for values in cleaned.values()):
        raise ValueError("필수 분석 항목이 비어 있습니다.")
    return InsightResult(**cleaned)


def _row_to_result(row) -> AnalysisResult:
    insights = InsightResult(**{key: json.loads(row[key]) for key in InsightResult.model_fields})
    return AnalysisResult(
        row["date_from"], row["date_to"], row["category"], row["article_count"], insights,
        json.loads(row["article_ids"]), json.loads(row["category_counts"]),
        row["ai_provider"], row["ai_model"], row["id"], row["excluded_count"],
    )
