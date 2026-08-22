"""기간·카테고리별 인사이트 분석 서비스 계약."""

from news_pipeline.models import AnalysisResult


class AnalyzerService:
    def analyze(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
        category: str | None,
        limit: int | None,
    ) -> AnalysisResult:
        raise NotImplementedError("Issue #8에서 인사이트 분석을 구현하세요.")

    def list_results(self) -> list[AnalysisResult]:
        raise NotImplementedError("Issue #8에서 분석 결과 조회를 구현하세요.")

    def get_result(self, result_id: int) -> AnalysisResult | None:
        raise NotImplementedError("Issue #8에서 분석 결과 조회를 구현하세요.")
