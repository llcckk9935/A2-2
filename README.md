# A2-2 — AI 뉴스 트렌드 및 종합 분석

아이뉴스24의 정치·경제·사회·IT 뉴스를 RSS와 기사 페이지 크롤링으로 수집하고,
정제·AI 요약·종합 분석·시각화·리포트·파일 내보내기까지 수행하는 CLI 기반 Python 프로젝트입니다.

## 주요 기능

- `fetch`: RSS 수집, 기사 본문 크롤링, raw SQLite 저장, skip/upsert 중복 처리
- `clean`: 필수 필드 검증, HTML 엔티티·태그·공백 정리, URL·날짜 정규화, clean 저장
- `summarize`: OpenAI 또는 Mock으로 3~5문장 요약과 핵심 내용 생성·저장
- `analyze`: 기간·카테고리별 트렌드, 키워드, 주요 이슈, 공통점·차이점, 시사점 분석·조회
- `report`: 실제 SQLite 집계로 차트 2종과 품질 지표·TOP N·AI 인사이트 리포트 생성
- `export`: 정제 뉴스를 CSV, JSONL, Excel로 내보내기

## 개발 환경

- Python 3.10 이상
- Windows 또는 macOS
- SQLite
- OpenAI API 또는 API 키가 필요 없는 Mock Provider

## 설치

### Windows PowerShell

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python main.py --help
pytest -q
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python main.py --help
pytest -q
```

PowerShell 실행 정책 변경은 현재 터미널 프로세스에만 적용됩니다.

## 설정과 API 키

뉴스 URL, 타임아웃, 요청 간격, 중복 정책, DB·로그·출력 경로, AI 모델은
[`config.json`](config.json)에서 관리합니다. 실제 OpenAI 호환 모드를 사용할 때만 `.env`에 키를 넣습니다. 교육장 Codyssey API는 기본 설정의 `https://copa.codyssey.kr/v1` 및 `gpt-5-mini`를 사용하며, OpenAI 호환 Chat Completions 방식으로 호출합니다.

```dotenv
OPENAI_API_KEY=실제_API_키
```

`.env`, API 키, 로컬 DB, 로그, 생성 리포트는 `.gitignore`로 제외되며 GitHub에 올리지 않습니다.
기본 Provider는 `mock`이고, CLI의 `--provider` 값이 설정 파일보다 우선합니다.

## 전체 실행 예시

API 비용 없이 전체 흐름을 확인하는 예시입니다.

```bash
# 1. RSS에서 URL을 얻고 기사 본문까지 수집해 raw 저장
python main.py fetch --method all --category it --limit 10 --delay 1.5 --duplicate-policy skip

# 2. raw 데이터를 정제해 clean 저장
python main.py clean --duplicate-policy upsert

# 3. 아직 요약되지 않은 기사 요약
python main.py summarize --unsummarized --limit 10 --provider mock

# 4. 요약 뉴스 종합 분석(최소 2건 필요)
python main.py analyze --category it --limit 10 --provider mock

# 5. 저장된 분석 결과 조회
python main.py analyze --list-results

# 6. 차트 2종과 Markdown 리포트 생성
python main.py report --category it --top-n 5 --format md

# 7. 파일 내보내기
python main.py export --format csv --status summarized
python main.py export --format jsonl --status all
python main.py export --format xlsx --status summarized
```

정치·경제·사회·IT 전체를 비교하려면 `--category all`을 사용하거나 카테고리를 생략합니다.

## CLI 상세 사용법

### 뉴스 수집

```bash
python main.py fetch --method rss --category politics --limit 20
python main.py fetch --method crawl --category economy --limit 10 --delay 1.5
python main.py fetch --method all --category all --limit 5 --duplicate-policy upsert
```

- `rss`: 제목·URL·발행일 등 RSS 메타데이터 수집
- `crawl`: RSS에서 얻은 URL의 기사 본문 크롤링
- `all`: 크롤링 실패 시 가능한 RSS 데이터라도 보존하는 부분 성공 방식
- `skip`: 기존 정규화 URL이면 건너뜀
- `upsert`: 기존 URL의 데이터를 최신 값으로 갱신

### 정제

```bash
python main.py clean --limit 20 --duplicate-policy skip
python main.py clean --all --duplicate-policy upsert
```

정제 결과는 raw와 분리된 `clean_news` 테이블에 저장됩니다. `--all`은 이미 정제된 raw도
다시 대상으로 선택하며, 재정제할 때는 보통 `upsert`를 함께 사용합니다.

### AI 요약

```bash
python main.py summarize --unsummarized --limit 10 --provider mock
python main.py summarize --id 42 --provider mock
python main.py summarize --all --force --limit 3 --provider openai
```

`--all`, `--id`, `--unsummarized`는 서로 동시에 사용할 수 없습니다. 이미 요약된 기사는
기본적으로 건너뛰며 `--force`일 때만 다시 요약합니다. 본문이 없으면 API를 호출하지 않습니다.

### AI 인사이트 분석과 조회

```bash
python main.py analyze --date-from 2026-08-20 --date-to 2026-08-26 --category it --provider mock
python main.py analyze --category all --limit 50 --provider openai
python main.py analyze --list-results
python main.py analyze --result-id 1
```

분석에는 요약 완료 뉴스가 최소 2건 필요합니다. 결과는 `analysis_results`에 영구 저장됩니다.

### 리포트와 내보내기

```bash
python main.py report --date-from 2026-08-20 --date-to 2026-08-26 --top-n 5 --format txt
python main.py report --category all --format md --output reports/final
python main.py export --format csv --status summarized --category it
python main.py export --format jsonl --date-from 2026-08-20 --date-to 2026-08-26
python main.py export --format xlsx --output exports/final.xlsx
```

리포트에는 카테고리별 뉴스 수, 일자별 수집 추이 PNG, 정제·중복·요약·필수 필드·본문
품질 지표, 카테고리 TOP N, 최신 AI 인사이트가 포함됩니다.

## 데이터 흐름과 저장 위치

```text
아이뉴스24 RSS → 기사 크롤링 → raw_news
                              ↓
                         clean_news
                              ↓
                    OpenAI 또는 Mock 요약
                              ↓
                       analysis_results
                              ↓
                 PNG + TXT/MD + CSV/JSONL/XLSX
```

- DB: `data/news.db`
- 로그: `logs/app.log`
- 차트·리포트: `reports/`
- 내보내기: `exports/`

raw는 외부에서 받은 원본과 수집 정보를 보존하여 재정제·오류 추적에 사용하고, clean은
분석에 적합하도록 정규화된 데이터를 보관합니다.

## RSS와 크롤링 비교

| 방식 | 장점 | 단점 |
|---|---|---|
| RSS | 구조가 비교적 안정적이고 요청 수가 적음 | 전문이 없거나 항목 수가 제한될 수 있음 |
| 크롤링 | 기사 본문을 확보할 수 있음 | HTML 변경, robots.txt, 요청 제한에 영향을 받음 |

이 프로젝트는 동일한 아이뉴스24 소스를 사용하여 데이터 일관성을 유지합니다.

## 크롤링 정책

- `robots.txt` 허용 여부를 먼저 확인합니다.
- 기본 요청 간격은 1.5초이며 `--delay`로 늘릴 수 있습니다.
- 타임아웃과 HTTP 오류를 처리하고, 429·유료 기사·본문 미발견은 실패로 기록합니다.
- 과도한 요청을 하지 않으며 교육·검증 목적의 소량 데이터만 수집합니다.
- 사이트 정책이나 구조가 바뀌면 수집을 중단하고 설정과 선택자를 재검토합니다.

## 테스트

```bash
pytest -q
git diff --check
```

자동 테스트는 임시 SQLite, 고정 RSS/HTML, Mock AI를 사용하므로 실제 사이트나 OpenAI를
호출하지 않습니다. Windows·Ubuntu·macOS에서 GitHub Actions 테스트도 실행됩니다.

## 정기 실행 예시(보너스)

macOS/Linux cron에서 매일 오전 9시에 RSS 수집:

```cron
0 9 * * * cd /path/to/A2-2 && .venv/bin/python main.py fetch --method rss --category all --limit 20
```

Windows에서는 작업 스케줄러에서 프로그램을 `.venv\Scripts\python.exe`, 인수를
`main.py fetch --method rss --category all --limit 20`, 시작 위치를 저장소 경로로 지정합니다.

## 문제 해결

- `Activate.ps1` 실행 차단: 위의 `Set-ExecutionPolicy -Scope Process ...`를 먼저 실행합니다.
- 분석 대상 0건: 수집 후 `clean`, `summarize`를 순서대로 실행하고 요약 완료 뉴스가 2건 이상인지 확인합니다.
- OpenAI 키 오류: `.env`의 `OPENAI_API_KEY`를 확인하거나 `--provider mock`을 사용합니다.
- 한글 차트 깨짐: Windows는 맑은 고딕, macOS는 AppleGothic, 그 외에는 NanumGothic을 설치합니다.
- 크롤링 실패: `logs/app.log`, robots.txt, 사이트 HTML 선택자와 요청 제한을 확인합니다.

## 프로젝트 구조

```text
A2-2/
├── main.py
├── config.json
├── news_pipeline/
│   ├── collectors/       # HTTP 요청과 RSS/HTML 파싱
│   ├── providers/        # OpenAI·Mock 공통 인터페이스
│   ├── services/         # 수집·정제·요약·분석·출력 흐름
│   ├── cli.py
│   ├── config.py
│   ├── database.py
│   ├── logger.py
│   └── models.py
├── tests/
├── docs/
├── data/
├── logs/
├── reports/
└── exports/
```

설계는 [`docs/architecture.md`](docs/architecture.md), 요구사항 검증은
[`docs/requirements-checklist.md`](docs/requirements-checklist.md), 협업 절차는
[`docs/team-workflow-guide.md`](docs/team-workflow-guide.md)를 참고하세요.
