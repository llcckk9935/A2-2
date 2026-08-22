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
