"""차트와 종합 리포트 생성 서비스 계약."""

from pathlib import Path


class ReporterService:
    def generate(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
        category: str | None,
        top_n: int,
        output_format: str,
        output: str | None,
    ) -> list[Path]:
        raise NotImplementedError("Issue #9에서 리포트 생성을 구현하세요.")

    def _fetch_mock_news(self) -> list[dict]:
        """임시 mock 뉴스 데이터. 나중에 실제 DB 조회 함수로 교체 예정."""
        return [
            {
                "id": 1,
                "source": "inews24",
                "category": "IT",
                "title": "AI 반도체 시장 급성장",
                "canonical_url": "https://example.com/1",
                "published_at": "2026-08-20",
                "summary_status": "summarized",
                "summary": "AI 반도체 수요가 늘고 있다.",
                "key_points": ["수요 증가", "가격 상승"],
                "summarized_at": "2026-08-20T10:00:00",
                "created_at": "2026-08-20T09:00:00",
                "updated_at": "2026-08-20T09:00:00",
            },
            {
                "id": 2,
                "source": "inews24",
                "category": "economy",
                "title": "금리 동결 발표",
                "canonical_url": "https://example.com/2",
                "published_at": "2026-08-21",
                "summary_status": "summarized",
                "summary": "한국은행이 금리를 동결했다.",
                "key_points": ["금리 동결", "물가 안정"],
                "summarized_at": "2026-08-21T10:00:00",
                "created_at": "2026-08-21T09:00:00",
                "updated_at": "2026-08-21T09:00:00",
            },
        ]