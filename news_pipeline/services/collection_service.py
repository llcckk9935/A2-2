"""RSS 수집과 기사 크롤링을 조정하는 서비스 계약.

Collector는 HTTP 요청과 파싱 후 ``RawNews``를 반환하고, 이 서비스는
수집 순서·처리 제한·요청 지연·중복 정책·저장·실행 통계를 조정한다.
중복은 정규화된 URL로 판단하며 이 서비스가 ``skip`` 또는 ``upsert`` 정책을
선택하고, 실제 조회와 저장 SQL은 ``database.py``에 위임한다. 기사별 실패는
로그에 남긴 뒤 가능한 경우 다음 기사를 계속 처리하고, 실행 단위 집계와
대표 오류는 ``collection_runs``에 기록한다. 최초 오류를 대표 오류로 삼고
추가 오류가 있으면 ``(외 N건)``을 덧붙인다. 정상 0건과 전체 중복은
``completed``, 일부 실패는 ``partial``, 요청·파싱 또는 전체 처리가 실패하면
``failed``로 처리한다.
"""

from typing import Literal

from news_pipeline.models import RunStats


class CollectionService:
    def fetch(
        self,
        method: str,
        category: str,
        limit: int,
        delay: float,
        duplicate_policy: Literal["skip", "upsert"],
    ) -> RunStats:
        raise NotImplementedError("Issue #4와 #5에서 수집 흐름을 구현하세요.")
