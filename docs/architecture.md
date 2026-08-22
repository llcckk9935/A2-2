# 프로젝트 아키텍처

## 파이프라인

```text
CLI
→ RSS 수집 / 기사 크롤링
→ SQLite raw_news
→ 정제 및 중복 처리
→ SQLite clean_news
→ Gemini 또는 Mock 요약
→ 기간·카테고리별 AI 분석
→ 차트·리포트·내보내기
```

## 모듈 책임

- `cli.py`: 옵션 해석과 Service 호출만 담당한다.
- `collectors/`: RSS·기사 페이지의 HTTP 요청과 응답 파싱만 담당하고, 결과를 `RawNews`로 반환한다. SQL 실행, SQLite 저장, 중복 정책 적용은 하지 않는다.
- `services/`: 기능별 업무 흐름과 검증을 담당한다.
- `collection_service.py`: RSS 수집기와 기사 크롤러의 실행 순서를 조정하고 `limit`, 요청 지연, 중복 정책, 저장 요청, 실행 통계를 관리한다. SQLite 접근은 `database.py`의 함수를 통해서만 수행한다.
- `providers/`: AI 인증, 호출, 재시도, 응답 변환을 담당한다.
- `database.py`: 모든 SQL과 SQLite 접근을 담당한다.
- `models.py`: 모듈 사이에서 공유하는 데이터 구조를 정의한다.

## 데이터베이스

- `raw_news`: 원본 수집 데이터
- `clean_news`: 검증·정규화된 뉴스와 요약
- `analysis_results`: 저장된 AI 인사이트
- `collection_runs`: 수집 실행 통계와 오류

날짜·시각은 SQLite에 UTC ISO 8601 문자열로 저장한다. 분석·리포트·내보내기는 `published_at`, 일자별 수집 추이는 `collected_at`을 기준으로 한다.

## 공통 규칙

- 중복 정책 우선순위: CLI → `config.json` → `skip`
- API 키: `GEMINI_API_KEY` 환경변수 또는 `.env`
- 경로 처리: `pathlib.Path`
- 실제 SQL: `database.py`에만 작성

## 수집 실패 처리

- 기사별 실패는 기사 URL 또는 ID, 실패 단계, 오류 원인을 로그 파일에 기록한다.
- 한 기사에서 오류가 발생해도 가능한 경우 다음 기사의 처리를 계속한다.
- RSS 정보 수집에는 성공했지만 본문 크롤링에 실패한 경우 RSS 원본은 `raw_news`에 저장하고, 크롤링 실패는 로그에 남긴다.
- 수집 실행의 성공·실패·중복 건수와 최종 상태는 `collection_runs`에 집계한다.
- 일부 항목만 실패하면 실행 상태를 `partial`, 실행 전체가 실패하면 `failed`로 저장한다.
- `collection_runs.error_message`에는 실행 전체 실패 원인 또는 대표 오류 요약을 저장하며, 기사별 상세 오류는 로그에서 확인한다.
