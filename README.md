# A2-2 AI 뉴스 트렌드 및 종합 분석

아이뉴스24 RSS와 기사 페이지에서 뉴스를 수집하고, 정제·AI 요약·인사이트 분석·시각화·리포트·내보내기를 수행하는 CLI 기반 Python 프로젝트입니다.

> 현재 상태: Issue #1 프로젝트 기본 틀입니다. CLI와 공통 계약은 준비됐지만 각 기능의 실제 구현은 담당 Issue에서 진행합니다.

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

설계 설명은 [`docs/architecture.md`](docs/architecture.md), 협업 규칙은 [`docs/collaboration.md`](docs/collaboration.md)를 참고합니다.

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
