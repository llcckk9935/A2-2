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
- `collectors/`: 네트워크 수집과 HTML 파싱을 담당한다.
- `services/`: 기능별 업무 흐름과 검증을 담당한다.
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
- 외부 호출 실패: 해당 항목을 기록하고 가능한 경우 다음 항목을 계속 처리
- 실제 SQL: `database.py`에만 작성
