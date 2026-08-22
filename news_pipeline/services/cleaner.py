"""raw 뉴스를 clean 뉴스로 변환하는 서비스 계약."""

from news_pipeline.models import CleanNews, RawNews, RunStats


class CleanerService:
    def clean_one(self, raw_news: RawNews) -> CleanNews:
        raise NotImplementedError("Issue #6에서 정제 규칙을 구현하세요.")

    def run(self, *, include_all: bool, limit: int | None, duplicate_policy: str) -> RunStats:
        raise NotImplementedError("Issue #6에서 정제 실행 흐름을 구현하세요.")
