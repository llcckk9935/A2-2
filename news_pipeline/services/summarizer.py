"""clean_news의 본문을 구조화된 AI 요약으로 저장한다."""

from __future__ import annotations

import json
import logging
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from news_pipeline.config import AIConfig
from news_pipeline.database import connect
from news_pipeline.models import RunStats, SummaryResult
from news_pipeline.providers.base import AIProvider, AIProviderError


class SummarizerService:
    def __init__(self, database_path: Path, ai_config: AIConfig, provider: AIProvider):
        self.database_path, self.ai_config, self.provider = database_path, ai_config, provider
        self.logger = logging.getLogger(__name__)

    def summarize(self, *, news_id: int | None, all_news: bool, unsummarized: bool, limit: int | None, force: bool) -> RunStats:
        stats = RunStats()
        sql, params = "SELECT * FROM clean_news", []
        if news_id is not None:
            sql += " WHERE id = ?"
            params.append(news_id)
        elif unsummarized:
            sql += " WHERE summary_status != 'summarized'"
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with closing(connect(self.database_path)) as connection:
            rows = connection.execute(sql, params).fetchall()
            stats.requested_count = len(rows)
            self.logger.info("요약 대상 %s건, provider=%s, model=%s", len(rows), self.provider.provider_name, self.provider.model_name)
            for row in rows:
                if row["summary_status"] == "summarized" and not force:
                    stats.skipped_count += 1
                    self.logger.info("기존 요약 스킵: news_id=%s", row["id"])
                    continue
                content = (row["content"] or "").strip()
                if not content:
                    connection.execute("UPDATE clean_news SET summary_status='not_ready', summary_error=?, updated_at=? WHERE id=?", ("본문이 없습니다.", _now(), row["id"]))
                    stats.skipped_count += 1
                    self.logger.warning("본문 누락: news_id=%s", row["id"])
                    continue
                original_length = len(content)
                content = content[: self.ai_config.max_input_chars]
                if len(content) < original_length:
                    self.logger.warning("본문 길이 제한: news_id=%s, original=%s, used=%s", row["id"], original_length, len(content))
                try:
                    result = self.provider.generate_json("summary", _summary_prompt(row, content), SummaryResult, {"title": row["title"]})
                    validated = _validate_summary(result)
                    connection.execute(
                        """UPDATE clean_news SET summary=?, key_points=?, summary_status='summarized', summary_error=NULL,
                           summarized_at=?, ai_provider=?, ai_model=?, updated_at=? WHERE id=?""",
                        (validated.summary, json.dumps(validated.key_points, ensure_ascii=False), _now(), self.provider.provider_name, self.provider.model_name, _now(), row["id"]),
                    )
                    stats.success_count += 1
                    self.logger.info("요약 완료: news_id=%s", row["id"])
                except (AIProviderError, ValueError) as exc:
                    connection.execute("UPDATE clean_news SET summary_status='failed', summary_error=?, updated_at=? WHERE id=?", (str(exc), _now(), row["id"]))
                    stats.failure_count += 1
                    self.logger.error("요약 실패: news_id=%s, error=%s", row["id"], exc)
            connection.commit()
        self.logger.info("요약 종료: 성공=%s 실패=%s 스킵=%s", stats.success_count, stats.failure_count, stats.skipped_count)
        return stats


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary_prompt(row, content: str) -> str:
    return f"""다음 뉴스 기사만 근거로 한국어 요약을 만드세요. 외부 사실, 주관적 평가, 광고/기자 소개를 추가하지 마세요.
핵심 내용을 3~5문장으로 요약하고 핵심 사항 2~3개를 추출하세요. JSON 외의 텍스트나 Markdown을 출력하지 마세요.
제목: {row['title']}
카테고리: {row['category']}
발행일: {row['published_at'] or '알 수 없음'}
본문:\n{content}"""


def _validate_summary(value: dict) -> SummaryResult:
    result = SummaryResult.model_validate(value)
    points = list(dict.fromkeys(point.strip() for point in result.key_points if point.strip()))
    if not result.summary.strip() or len(points) < 2:
        raise ValueError("요약 또는 핵심 내용이 비어 있거나 중복되어 유효하지 않습니다.")
    return SummaryResult(summary=result.summary.strip(), key_points=points)
