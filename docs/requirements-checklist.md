# Project B 요구사항 검증 체크리스트

이 문서는 과제 본문의 필수 요구사항이 코드·테스트·수동 검증에 반영되었는지 확인하는 최종 점검표입니다.

## 1. CLI 설계

- [x] `argparse` 기반 서브커맨드 구조를 사용한다.
- [x] `fetch`, `clean`, `summarize`, `analyze`, `report`, `export`를 제공한다.
- [x] `--limit`, `--category`, `--date`/기간, `--format` 등 필요한 옵션을 제공한다.
- [x] 상호 배타 옵션과 잘못된 날짜 범위를 검증한다.
- [x] 모든 명령에서 `--help`를 제공한다.

검증: `tests/test_cli.py`, `python main.py --help`

## 2. 뉴스 수집과 raw 저장

- [x] 공개 RSS로 정치·경제·사회·IT 뉴스를 수집한다.
- [x] BeautifulSoup으로 기사 페이지의 본문을 크롤링한다.
- [x] HTTP 요청에 타임아웃과 User-Agent를 설정한다.
- [x] 연결·응답·파싱·429·본문 없음 오류를 기사별로 처리하고 다음 처리를 계속한다.
- [x] `robots.txt`를 확인하고 요청 간 지연을 적용한다.
- [x] 수집 시각, 소스, 수집 방법, 원본 payload를 `raw_news`에 저장한다.
- [x] `--limit`을 초과하여 저장하지 않는다.
- [x] 정규화 URL을 기준으로 `skip`과 `upsert` 정책을 적용한다.
- [x] 실행 통계를 `collection_runs`에 저장한다.

검증: `tests/test_collectors.py`, `tests/test_article_crawler.py`, `tests/test_collection_service.py`

## 3. 데이터 정제와 clean 저장

- [x] 제목·URL 필수 필드를 검증한다.
- [x] HTML 엔티티·태그·중복 공백을 정규화한다.
- [x] 추적 쿼리와 fragment를 제거하여 URL을 정규화한다.
- [x] RSS/ISO 날짜를 ISO 8601 형식으로 통일하고 잘못된 값은 결측 처리한다.
- [x] 본문 결측을 빈 문자열로 처리한다.
- [x] `skip`/`upsert` 중복 정책을 적용한다.
- [x] raw와 분리된 `clean_news`에 영구 저장한다.

검증: `tests/test_cleaning.py`

## 4. AI 뉴스 요약

- [x] OpenAI 공식 SDK 호출과 API 키 없는 Mock Provider를 제공한다.
- [x] `--all`, `--id`, `--unsummarized`, `--limit`, `--force`를 제공한다.
- [x] 이미 요약된 기사는 기본 스킵한다.
- [x] 본문이 없으면 API 호출 없이 `not_ready`로 처리한다.
- [x] 입력 길이와 최대 출력 토큰을 제한한다.
- [x] 요약문과 핵심 내용의 JSON 구조를 검증한다.
- [x] API 인증·요청 제한·타임아웃·응답 오류를 구분하고 실패 기사만 건너뛴다.
- [x] 요약, 핵심 내용, 상태, 시각, Provider·모델을 SQLite에 저장한다.
- [x] Mock 결과에 입력 기사 제목이 포함된다.

검증: `tests/test_ai_providers.py`, `tests/test_ai_services.py`

## 5. AI 인사이트 분석

- [x] 기간과 카테고리로 요약 뉴스를 선택한다.
- [x] 주요 트렌드, 핵심 키워드, 주요 이슈, 공통점, 차이점, 시사점을 분석한다.
- [x] 알려진 기본 카테고리와 상세 카테고리 모두 균형 선택할 수 있다.
- [x] 분석 결과와 사용 기사 ID·카테고리 집계를 `analysis_results`에 저장한다.
- [x] `--list-results`, `--result-id`로 저장 결과를 조회한다.
- [x] 최소 기사 수 미달을 사용자에게 명확히 알린다.

검증: `tests/test_ai_services.py`

## 6. 시각화와 리포트

- [x] 실제 SQLite 데이터로 카테고리별 뉴스 수 막대 차트를 생성한다.
- [x] 실제 SQLite 데이터로 일자별 뉴스 추이 선 차트를 생성한다.
- [x] Windows·macOS·Nanum 한글 폰트를 탐색해 적용한다.
- [x] 차트를 PNG로 저장한다.
- [x] 정제율·중복률·요약률·필수 필드 완성률·본문 확보율을 포함한다.
- [x] 카테고리 TOP N을 포함한다.
- [x] 최신 AI 인사이트를 포함한다.
- [x] 콘솔 출력과 TXT/MD 파일 저장을 지원한다.

검증: `tests/test_reporter.py`

## 7. 데이터 내보내기

- [x] CSV, JSONL, Excel 세 형식을 지원한다.
- [x] `--status summarized`와 `unsummarized` 필터를 지원한다.
- [x] 카테고리와 기간 필터를 지원한다.
- [x] 누락 날짜를 기간 필터에서 안전하게 제외한다.
- [x] 전체 행을 내보내며 같은 시각의 파일명 충돌을 방지한다.
- [x] Excel 헤더·줄바꿈·열 너비를 적용한다.
- [x] 기존 명시 파일을 실수로 덮어쓰지 않는다.

검증: `tests/test_exporter.py`

## 8. 설정·로깅·저장·구조

- [x] `config.json`으로 API 환경변수명, URL, 모델, 제한, 중복 정책, 경로를 관리한다.
- [x] API 키는 `OPENAI_API_KEY` 환경변수에서만 읽는다.
- [x] `.env`, DB, 로그, 결과 파일은 `.gitignore`로 제외한다.
- [x] `logging`의 INFO/WARNING/ERROR와 회전 파일 로그를 사용한다.
- [x] SQLite를 영구 저장소로 사용하며 List/Dict만으로 보관하지 않는다.
- [x] collectors/providers/services/DB/CLI 등 4개 이상의 모듈로 분리한다.
- [x] Windows와 macOS 설치·실행법을 README에 작성한다.

검증: `tests/test_config.py`, `tests/test_database.py`, `tests/test_cli.py`

## 9. 전체 연결과 품질

- [x] 수집 → raw → clean → Mock 요약 → Mock 분석 → 리포트 → CSV/JSONL/Excel을 연결한다.
- [x] 자동 테스트에서는 실제 뉴스 사이트와 OpenAI API를 호출하지 않는다.
- [x] Windows·Ubuntu·macOS GitHub Actions 테스트를 구성한다.
- [x] `git diff --check`로 공백 오류를 검사한다.
- [ ] 실제 OpenAI API로 소량 요약·분석을 최종 1회 검증한다.
- [ ] 최종 `main`에서 전체 테스트와 대표 CLI 시연을 다시 수행한다.

검증: `tests/test_pipeline.py`, `.github/workflows/tests.yml`

## 10. 보너스

- [ ] `list`, `show` 뉴스 조회 서브커맨드와 페이지네이션
- [ ] 감성 분석과 감성 차트
- [x] cron과 Windows 작업 스케줄러 안내

보너스 미구현 항목은 과제 필수 제출 조건이 아닙니다.

## 최종 수동 검증 명령

```bash
pytest -q
git diff --check
python main.py --help
python main.py fetch --method all --category it --limit 3 --delay 1.5 --duplicate-policy upsert
python main.py clean --all --duplicate-policy upsert
python main.py summarize --unsummarized --limit 3 --provider mock
python main.py analyze --category it --limit 3 --provider mock
python main.py report --category it --top-n 3 --format md
python main.py export --format csv --status summarized
python main.py export --format jsonl --status all
python main.py export --format xlsx --status summarized
```

OpenAI 키가 준비된 환경에서는 Mock 명령 중 요약·분석 각 1회를 `--provider openai`로 별도 실행합니다.
