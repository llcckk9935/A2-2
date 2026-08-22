"""아이뉴스24 RSS 수집기 계약."""

from __future__ import annotations

from news_pipeline.models import RawNews


class RSSCollector:
    def fetch(self, category: str, limit: int) -> list[RawNews]:
        """RSS에서 최대 limit건을 가져온다. Issue #4에서 구현한다."""

        raise NotImplementedError("Issue #4에서 RSS 수집을 구현하세요.")
