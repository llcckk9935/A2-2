# A2-2 AI 뉴스 트렌드 및 종합 분석

아이뉴스24 RSS와 기사 페이지에서 뉴스를 수집하고, 정제·AI 요약·인사이트 분석·시각화·리포트·내보내기를 수행하는 CLI 기반 Python 프로젝트입니다.

> AI 요약과 인사이트 분석은 Gemini/Mock Provider를 통해 실행할 수 있습니다. 수집·정제·리포트 등 나머지 기능은 담당 Issue에서 확장합니다.

## 개발 환경

- Python 3.10 이상
- Windows 또는 macOS
- SQLite
- Gemini API와 API 키 없는 Mock 모드

## 빠른 시작

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python main.py --help
pytest
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python main.py --help
pytest
```

실제 Gemini 모드를 사용할 팀원만 `.env`의 값을 자신의 키로 변경합니다.

```dotenv
GEMINI_API_KEY=실제_API_키
```

`.env`와 실제 API 키는 GitHub에 올리지 않습니다.

## CLI 구조

```text
python main.py fetch       # RSS 수집 및 기사 크롤링
python main.py clean       # raw 뉴스 정제
python main.py summarize   # Gemini 또는 Mock 뉴스 요약
python main.py analyze     # 기간·카테고리별 인사이트 분석 및 조회
python main.py report      # 차트와 TXT/MD 리포트 생성
python main.py export      # CSV·JSONL·Excel 내보내기
```

자세한 옵션은 명령별 도움말로 확인합니다.

```bash
python main.py fetch --help
python main.py summarize --help
python main.py export --help
```

## AI 뉴스 요약과 인사이트 분석

API 키 없이 개발·테스트하려면 결정적인 결과를 반환하는 Mock Provider를 사용합니다.

```bash
python main.py summarize --unsummarized --limit 10 --provider mock
python main.py summarize --id 42 --provider mock
python main.py summarize --all --force --limit 3 --provider mock
python main.py analyze --date-from 2026-08-20 --date-to 2026-08-26 --provider mock
python main.py analyze --date-from 2026-08-20 --date-to 2026-08-26 --category it --limit 10 --provider mock
python main.py analyze --list-results
python main.py analyze --result-id 3
```

Gemini를 사용할 때만 `GEMINI_API_KEY`를 설정한 뒤 `--provider gemini`로 실행합니다. 요약은 기사 본문을 구조화된 JSON(`summary`, `key_points`)으로 받고 SQLite의 `clean_news`에 저장합니다. 분석은 저장된 요약문을 바탕으로 주요 트렌드, 키워드, 이슈, 공통점, 차이점, 시사점을 생성해 `analysis_results`에 별도로 저장합니다.

Gemini 무료 등급에는 요청·토큰 제한이 있으므로 실제 검증은 `--limit 3`처럼 작은 수로 실행합니다. 무료 등급의 입력이 제품 개선에 사용될 수 있으므로 공개 뉴스 외 개인정보, 비공개 정보, API 키는 프롬프트에 넣지 마세요. 자동 테스트는 항상 Mock Provider만 사용하며 실제 API 호출을 하지 않습니다.

## 프로젝트 구조

```text
A2-2/
├── main.py
├── config.json
├── news_pipeline/
│   ├── collectors/       # RSS와 기사 크롤링
│   ├── providers/        # Gemini와 Mock Provider
│   ├── services/         # 수집·정제·AI·출력 업무 흐름
│   ├── cli.py
│   ├── config.py
│   ├── database.py
│   ├── logger.py
│   └── models.py
├── tests/
├── data/
├── logs/
├── reports/
├── exports/
└── docs/
```

설계 설명은 [`docs/architecture.md`](docs/architecture.md), 핵심 협업 규칙은 [`docs/collaboration.md`](docs/collaboration.md), 역할별 전체 작업 절차는 [`docs/team-workflow-guide.md`](docs/team-workflow-guide.md)를 참고합니다.

## 데이터와 생성 파일

다음 파일은 각 컴퓨터에만 보관하며 GitHub에 올리지 않습니다.

- `data/news.db`
- `logs/*.log`
- `reports/*`
- `exports/*`
- `.env`

## 테스트

```bash
pytest
```

표준 라이브러리만으로 테스트 실행기를 확인하려면 다음 명령도 사용할 수 있습니다.

```bash
python -m unittest discover -v
```

자동 테스트에서는 실제 아이뉴스24와 Gemini API를 호출하지 않습니다. 실제 연결 검증은 제출 전 별도 수동 점검으로 진행합니다.
