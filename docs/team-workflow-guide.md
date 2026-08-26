# A2-2 팀 개발·협업 가이드

이 문서는 A2-2 팀원과 팀장이 같은 방식으로 개발하고 검토하기 위한 공통 가이드입니다.

- 공식 마감일: 2026-08-27
- 내부 개발·통합 마감일: 2026-08-26
- 저장소: <https://github.com/llcckk9935/A2-2>
- 개발 방식: Issue → 개인 브랜치 → 구현·테스트 → 커밋 → push → Pull Request → 리뷰 → Squash merge

---

## 1. 최종 역할 분담

| 담당자 | 담당 Issue | 주요 작업 |
|---|---:|---|
| 이충관(팀장) | #1, #2, #12 | 기본 틀, 설정·로깅, CLI, README, 최종 통합 |
| 신지수 | #3, #6 | SQLite, raw/clean 저장, 데이터 정제, 중복 처리 |
| 유도현 | #4, #5 | RSS 수집, 기사 본문 크롤링 |
| 김주원 | #7, #8 | OpenAI·Mock 요약, AI 인사이트 분석 |
| 전종혁 | #9, #10 | 시각화, 리포트, CSV·JSONL·Excel 내보내기 |
| 김의종 | #11 | 통합 테스트, 요구사항 검증, 실행 검증 보조 |

모든 팀원이 저장소 초대를 수락한 뒤 GitHub Assignee를 일괄 지정합니다. Assignee 지정 전에도 위 표의 역할은 그대로 유효합니다.

---

## 2. 모든 팀원이 지켜야 할 핵심 규칙

1. `main` 브랜치에서 직접 개발하거나 push하지 않습니다.
2. 원칙적으로 **Issue 하나당 브랜치 하나, PR 하나**를 사용합니다.
3. 작업 시작 전 반드시 최신 `main`에서 새 브랜치를 만듭니다.
4. 담당 Issue 본문의 작업 내용과 완료 조건을 먼저 읽습니다.
5. 구현한 기능에는 필요한 테스트를 작성하거나 기존 테스트를 수정합니다.
6. “커밋 완료”만 보고하지 말고 GitHub에 push하고 PR 링크를 전달합니다.
7. PR의 GitHub Actions가 모두 성공하고 팀장이 변경 내용을 확인한 뒤 병합합니다. 팀원 승인은 권장하지만 필수는 아닙니다.
8. `.env`, OpenAI API 키, 개인 DB, 로그, 생성 리포트는 GitHub에 올리지 않습니다.
9. 다른 담당자의 파일이나 공용 인터페이스를 변경해야 하면 먼저 Issue 댓글이나 팀 채팅으로 알립니다.
10. 문제가 생기면 임의로 강제 push하거나 파일을 삭제하지 말고 팀장에게 현재 명령과 오류 화면을 전달합니다.

---

## 3. 팀원 작업 절차

### 3.1 최초 한 번: 개발환경 준비

#### Windows PowerShell

```powershell
git clone https://github.com/llcckk9935/A2-2.git
cd A2-2

py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env

python main.py --help
pytest -q
```

#### macOS

```bash
git clone https://github.com/llcckk9935/A2-2.git
cd A2-2

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env

python main.py --help
pytest -q
```

정상 기준:

- `python main.py --help`에 `fetch`, `clean`, `summarize`, `analyze`, `report`, `export`가 표시됩니다.
- 전체 테스트가 실패 없이 통과합니다.
- `.env`는 각자의 컴퓨터에만 존재하며 GitHub에 올라가지 않습니다.

실제 OpenAI API가 필요하지 않은 개발과 단위 테스트에서는 `mock` Provider를 사용합니다.

---

### 3.2 작업 시작 알림

담당 Issue에 다음과 같이 댓글을 남깁니다.

```text
작업 시작하겠습니다.

- 담당 기능: 구현할 기능
- 예상 변경 파일: 변경할 파일
- 테스트 계획: 실행하거나 작성할 테스트
```

Issue가 두 개라면 각 Issue의 작업 범위를 확인합니다. 두 Issue를 하나의 브랜치에서 작업해야 할 특별한 이유가 있으면 먼저 팀장과 협의합니다.

---

### 3.3 최신 main 확인

작업을 시작할 때마다 실행합니다.

```bash
git switch main
git pull origin main
git status --short
```

`git status --short`에 아무것도 출력되지 않아야 정상입니다.

변경 파일이 출력되면 새 브랜치를 만들기 전에 팀장에게 알립니다. 임의로 삭제하거나 되돌리지 않습니다.

---

### 3.4 Issue 전용 브랜치 만들기

브랜치 이름 형식:

```text
feature/Issue번호-간단한-기능명
```

예시:

```bash
git switch -c feature/4-rss-collector
git switch -c feature/7-ai-summary
git switch -c feature/9-visualization
```

브랜치를 만든 뒤 확인합니다.

```bash
git branch --show-current
```

결과가 `main`이면 작업하지 말고 Issue 전용 브랜치를 다시 만듭니다.

---

### 3.5 구현 중 확인 사항

- 담당 Issue의 완료 조건을 하나씩 확인하며 구현합니다.
- 기존 파일 구조와 함수 이름을 가능한 한 유지합니다.
- 서비스 계층에서 OpenAI SDK 응답 객체를 DB에 직접 넘기지 않습니다.
- Provider는 `openai`와 `mock`이 같은 입력·출력 계약을 따르게 합니다.
- 단위 테스트에서 실제 아이뉴스24 사이트나 OpenAI API를 호출하지 않습니다.
- 네트워크 요청에는 타임아웃과 오류 처리를 적용합니다.
- 한 건의 실패 때문에 전체 작업이 비정상 종료되지 않도록 합니다.
- API 키나 기사 전문을 로그에 출력하지 않습니다.

공용 파일 또는 담당 경계를 넘어서는 변경 예시:

- `database.py`의 테이블이나 함수 시그니처 변경
- `models.py`의 공용 모델 변경
- `config.json`의 구조 변경
- CLI 옵션 이름 변경
- 다른 팀원이 담당한 서비스 파일의 대규모 변경

이러한 변경은 구현 전에 팀장과 관련 담당자에게 알립니다.

---

### 3.6 테스트 실행

먼저 담당 기능 테스트를 실행합니다.

```bash
pytest tests/담당_테스트파일.py -q
```

그다음 전체 테스트를 실행합니다.

```bash
pytest -q
```

추가 확인:

```bash
python main.py --help
python main.py 담당명령 --help
```

테스트가 실패한 상태에서는 PR 병합을 요청하지 않습니다.

테스트 결과를 보고할 때는 `성공했습니다`만 쓰지 말고 다음처럼 작성합니다.

```text
pytest tests/test_ai_providers.py -q: 6 passed
pytest -q: 18 passed
python main.py summarize --help: 정상 출력
```

---

### 3.7 변경 내용 확인과 커밋

```bash
git status --short
git diff
```

담당 파일만 선택하여 추가합니다.

```bash
git add 변경한_파일1 변경한_파일2
git diff --cached --check
git diff --cached
```

커밋 메시지에는 Issue 번호를 넣습니다.

```bash
git commit -m "feat: implement AI summary (#7)"
```

권장 접두어:

| 접두어 | 용도 |
|---|---|
| `feat` | 기능 추가 |
| `fix` | 오류 수정 |
| `test` | 테스트 추가·수정 |
| `docs` | 문서 수정 |
| `refactor` | 기능 변화 없는 구조 개선 |
| `chore` | 설정·환경·기타 작업 |

커밋 후 확인합니다.

```bash
git status --short
git log -1 --oneline
```

`git status --short` 출력이 없으면 커밋되지 않은 변경이 없는 상태입니다.

---

### 3.8 GitHub에 push

현재 브랜치 이름을 확인합니다.

```bash
git branch --show-current
```

현재 브랜치를 push합니다.

```bash
git push -u origin 현재_브랜치명
```

중요:

- 커밋은 자신의 컴퓨터에 저장하는 작업입니다.
- push는 커밋을 GitHub에 올리는 작업입니다.
- 팀장은 push된 브랜치나 PR만 검토할 수 있습니다.

---

### 3.9 Pull Request 만들기

GitHub에서 다음 설정을 확인합니다.

- base: `main`
- compare: 자신의 Issue 브랜치
- 제목 예시: `[AI] OpenAI·Mock 뉴스 요약 구현 (#7)`
- 관련 Issue: `Closes #7`
- Milestone: `Project B 최종 완료`
- Assignee: 본인(초대 및 계정 확인 후)
- Reviewer: 팀장 또는 지정된 리뷰어

PR 템플릿의 빈칸을 모두 작성합니다.

- 무엇을 구현했는지
- 어떤 과제 요구사항을 충족하는지
- 어떤 명령으로 테스트했는지
- 테스트 결과가 몇 개 통과했는지
- DB·공용 인터페이스·설정 변경 여부
- 리뷰어가 집중해서 볼 부분

PR을 만든 뒤 팀 채팅에 다음처럼 보고합니다.

```text
PR 생성했습니다. 검토 부탁드립니다.

- 담당 Issue: #7
- 브랜치: feature/7-ai-summary
- PR 링크: GitHub_PR_주소
- 주요 변경: OpenAI·Mock 요약 및 결과 저장
- 테스트: 담당 테스트 6 passed, 전체 테스트 18 passed
- 확인 요청: 응답 JSON 검증과 실패 처리 부분
```

---

### 3.10 리뷰 수정 요청을 받은 경우

새 브랜치나 새 PR을 만들지 않고 기존 작업 브랜치에서 수정합니다.

```bash
git switch 기존_작업_브랜치
```

수정과 테스트를 마친 뒤:

```bash
git add 변경한_파일
git commit -m "fix: address review feedback (#7)"
git push
```

기존 PR에 새 커밋이 자동으로 반영됩니다. 수정한 내용과 재실행한 테스트 결과를 PR 댓글로 남깁니다.

충돌, rebase 또는 강제 push가 필요해 보이면 임의로 실행하지 말고 팀장에게 문의합니다.

---

## 4. 팀장이 해야 할 일

### 4.1 작업 시작 전 관리

- 모든 팀원의 저장소 초대 수락 여부를 확인합니다.
- 전원 수락 후 각 Issue의 Assignee를 지정합니다.
- 역할 분담과 담당 파일 경계를 팀 채팅에 고정합니다.
- Issue 본문과 완료 조건이 과제 요구사항을 빠뜨리지 않았는지 확인합니다.
- 내부 마감일인 2026-08-26을 반복해서 안내합니다.

---

### 4.2 팀원의 “커밋 완료” 보고를 받았을 때

다음 네 가지가 없으면 아직 검토 가능한 상태가 아닙니다.

1. 브랜치 이름
2. 마지막 커밋 정보
3. GitHub push 완료
4. PR 링크

팀원에게 다음 결과를 요청합니다.

```bash
git branch --show-current
git status --short
git log -1 --oneline
```

확인 기준:

- 브랜치가 `main`이 아닙니다.
- `git status --short` 출력이 없습니다.
- 커밋 메시지에 담당 Issue 번호가 있습니다.
- GitHub에 해당 브랜치와 PR이 존재합니다.

`main`에서 작업했다면 바로 push하지 않도록 안내하고, 별도 브랜치로 옮기는 절차를 진행합니다.

---

### 4.3 PR 검토 순서

1. PR의 base가 `main`인지 확인합니다.
2. `Closes #번호`가 담당 Issue와 일치하는지 확인합니다.
3. 변경 파일이 담당 범위와 맞는지 확인합니다.
4. `Files changed`에서 불필요한 대규모 변경이 없는지 확인합니다.
5. `.env`, API 키, DB, 로그, 생성 파일이 포함되지 않았는지 확인합니다.
6. Issue 완료 조건이 실제 코드와 테스트에 반영됐는지 확인합니다.
7. DB 스키마나 공용 함수 변경이 문서에 기록됐는지 확인합니다.
8. 테스트 코드가 실제 네트워크나 OpenAI API를 호출하지 않는지 확인합니다.
9. GitHub Actions의 Windows·macOS·Ubuntu 테스트가 모두 성공했는지 확인합니다.
10. 필요한 수정은 구체적인 파일·함수·이유와 함께 리뷰 댓글로 요청합니다.

PR 검토 결과는 다음 중 하나로 처리합니다.

- 문제 없음: `Approve`
- 반드시 수정 필요: `Request changes`
- 질문 또는 사소한 제안: 일반 `Comment`

---

### 4.4 병합 조건

다음 조건을 모두 만족한 경우에만 `Squash and merge`합니다.

- 담당 Issue 완료 조건 충족
- 전체 자동 테스트 성공
- 필요한 리뷰 대화 해결
- 팀장의 변경 내용 확인 완료
- 민감정보와 생성 파일 미포함
- 공용 인터페이스 변경 영향 확인

병합 후 확인합니다.

- PR 상태가 `Merged`
- `Closes #번호`를 사용했다면 Issue가 `Closed`
- Milestone 진행률 반영
- 원격 작업 브랜치 삭제

팀장 로컬 저장소도 갱신합니다.

```bash
git switch main
git pull origin main
pytest -q
git status --short
```

Issue #12는 모든 기능의 전체 연결 테스트와 최종 요구사항 검증이 끝날 때까지 종료하지 않습니다.

---

### 4.5 최종 통합 순서

기능 PR을 다음 의존 순서로 확인합니다.

```text
DB·저장 구조
→ RSS 수집·크롤링
→ 데이터 정제
→ OpenAI·Mock 요약
→ AI 인사이트 분석
→ 시각화·리포트
→ CSV·JSONL·Excel 내보내기
→ 전체 연결 테스트
```

최종 확인 항목:

- 필수 CLI 6개가 모두 실행됩니다.
- raw와 clean 데이터가 분리 저장됩니다.
- 중복 정책 `skip/upsert`가 동작합니다.
- OpenAI 및 Mock 요약이 동작합니다.
- 분석 결과가 저장되고 조회됩니다.
- 카테고리별·일자별 차트가 PNG로 생성됩니다.
- 품질 지표 2개 이상과 TOP N 집계가 리포트에 포함됩니다.
- TXT 또는 MD 리포트가 생성됩니다.
- CSV·JSONL·Excel 내보내기가 동작합니다.
- `--status summarized` 필터가 동작합니다.
- Windows와 macOS 실행 방법이 README에 있습니다.
- 실제 OpenAI API 호출은 최소 1회 수동으로 검증합니다.
- 전체 테스트와 GitHub Actions가 통과합니다.
- API 키와 개인정보가 저장소에 없습니다.

---

## 5. 문제 발생 시 행동

### `main`에서 작업한 경우

- 커밋이나 push를 더 진행하지 않습니다.
- `git branch --show-current`, `git status --short`, `git log -1 --oneline` 결과를 팀장에게 보냅니다.
- 팀장의 안내에 따라 작업 브랜치를 만듭니다.

### push에서 403 오류가 발생한 경우

- GitHub 저장소 초대 수락 여부를 확인합니다.
- 현재 로그인된 GitHub 계정을 확인합니다.
- 오류 화면 전체와 GitHub 아이디를 팀장에게 보냅니다.
- API 키나 비밀번호는 보내지 않습니다.

### 테스트가 실패한 경우

- 실패한 명령과 오류 메시지 전체를 전달합니다.
- 마지막 부분만 잘라서 보내지 않습니다.
- `passed` 같은 결과 문구를 PowerShell 명령으로 다시 입력하지 않습니다.

### merge conflict가 발생한 경우

- 임의로 `git push --force`를 실행하지 않습니다.
- 충돌 파일과 실행한 명령을 팀장에게 전달합니다.
- 팀장과 담당자가 함께 충돌 내용을 결정합니다.

### OpenAI API 키가 없는 경우

- `mock` Provider로 구현과 테스트를 진행합니다.
- 실제 OpenAI 호출은 키를 가진 팀원이 제출 전 별도로 확인합니다.

---

## 6. 팀 채팅 보고 양식

### 작업 시작

```text
Issue #번호 작업 시작합니다.
브랜치: feature/번호-기능명
예상 변경 파일: 파일 목록
```

### 막힘 보고

```text
Issue #번호 작업 중 문제가 발생했습니다.

- 실행한 명령:
- 발생한 오류:
- 현재 브랜치:
- 마지막 정상 단계:
- 오류 화면 또는 전체 로그:
```

### PR 검토 요청

```text
Issue #번호 PR 생성했습니다. 검토 부탁드립니다.

- 브랜치:
- PR 링크:
- 주요 변경:
- 담당 테스트 결과:
- 전체 테스트 결과:
- 확인이 필요한 부분:
```

### 리뷰 반영 완료

```text
리뷰 의견 반영 후 push했습니다.

- 반영 내용:
- 재실행한 테스트:
- 테스트 결과:
```

---

## 7. 팀원 최종 체크리스트

- [ ] 담당 Issue 본문과 완료 조건을 읽었다.
- [ ] 최신 `main`에서 Issue 전용 브랜치를 만들었다.
- [ ] `main`에 직접 작업하거나 push하지 않았다.
- [ ] 담당 범위의 코드와 테스트를 함께 작성했다.
- [ ] 실제 사이트와 OpenAI API를 단위 테스트에서 호출하지 않았다.
- [ ] 담당 테스트와 전체 테스트가 통과했다.
- [ ] `.env`, API 키, DB, 로그, 생성 파일을 커밋하지 않았다.
- [ ] 커밋 메시지에 Issue 번호를 작성했다.
- [ ] 현재 브랜치를 GitHub에 push했다.
- [ ] PR 템플릿을 빠짐없이 작성했다.
- [ ] PR 링크와 테스트 결과를 팀 채팅에 전달했다.
- [ ] 팀장이 확인하기 전에 직접 병합하지 않았다.

---

## 8. 팀장 최종 체크리스트

- [ ] 모든 팀원의 저장소 초대 수락 여부를 확인했다.
- [ ] 전원 수락 후 Issue Assignee를 지정했다.
- [ ] 역할과 파일 담당 경계를 공유했다.
- [ ] 각 PR의 변경 범위와 과제 요구사항을 검토했다.
- [ ] 민감정보와 불필요한 생성 파일이 없는지 확인했다.
- [ ] Windows·macOS·Ubuntu Actions 결과를 확인했다.
- [ ] 변경 내용과 테스트 결과를 확인하고 필요한 리뷰 대화를 해결한 후 Squash merge했다.
- [ ] 병합 후 Issue와 Milestone 상태를 확인했다.
- [ ] 로컬 `main`을 최신화하고 전체 테스트를 실행했다.
- [ ] Issue #12에서 전체 연결 테스트를 완료했다.
- [ ] 내부 마감일인 2026-08-26까지 최종 통합을 완료했다.