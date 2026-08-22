"""RSS 수집과 기사 크롤링을 조정하는 서비스 계약."""

from news_pipeline.models import RunStats


class CollectionService:
    def fetch(
        self,
        method: str,
        category: str,
        limit: int,
        delay: float,
        duplicate_policy: str,
    ) -> RunStats:
        raise NotImplementedError("Issue #4와 #5에서 수집 흐름을 구현하세요.")
