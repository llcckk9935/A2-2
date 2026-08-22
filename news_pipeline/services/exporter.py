"""CSV·JSONL·Excel 내보내기 서비스 계약."""

from pathlib import Path


class ExporterService:
    def export(
        self,
        *,
        output_format: str,
        status: str,
        category: str | None,
        date_from: str | None,
        date_to: str | None,
        output: str | None,
    ) -> Path:
        raise NotImplementedError("Issue #10에서 데이터 내보내기를 구현하세요.")
