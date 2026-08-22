"""뉴스 요약 서비스 계약."""

from news_pipeline.models import RunStats


class SummarizerService:
    def summarize(
        self,
        *,
        news_id: int | None,
        all_news: bool,
        unsummarized: bool,
        limit: int | None,
        force: bool,
    ) -> RunStats:
        raise NotImplementedError("Issue #7에서 뉴스 요약을 구현하세요.")
