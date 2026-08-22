"""아이뉴스24 기사 본문 크롤러 계약."""

from __future__ import annotations

from news_pipeline.models import RawNews


class ArticleCrawler:
    def crawl(self, news: RawNews, delay: float) -> RawNews:
        """RSS 뉴스 URL에서 본문을 보완한다. Issue #5에서 구현한다."""

        raise NotImplementedError("Issue #5에서 기사 크롤링을 구현하세요.")
