"""RSS 수집과 기사 크롤링을 조정하는 서비스 계약.

Collector는 HTTP 요청과 파싱 후 ``RawNews``를 반환하고, 이 서비스는
수집 순서·처리 제한·요청 지연·중복 정책·저장·실행 통계를 조정한다.
기사별 실패는 로그에 남긴 뒤 가능한 경우 다음 기사를 계속 처리하며,
실행 단위 집계는 ``collection_runs``에 기록한다. SQL은 직접 실행하지 않고
``database.py``가 제공하는 함수를 통해서만 SQLite에 접근한다.
"""

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
