# 협업 규칙

팀원별 역할, 개발환경 준비, 브랜치·커밋·PR 절차, 팀장 검토 방법과 보고 양식은 [팀 개발·협업 상세 가이드](team-workflow-guide.md)를 참고한다.

## 담당 경계

| 담당 | 주요 파일 |
|---|---|
| 팀장 | `main.py`, `cli.py`, `config.py`, `logger.py`, `config.json`, `requirements.txt`, `README.md` |
| 팀원 A | `database.py`, `models.py`, `cleaner.py` |
| 팀원 B | `collectors/`, `collection_service.py` |
| 팀원 C | `providers/`, `summarizer.py`, `analyzer.py` |
| 팀원 D | `reporter.py`, `exporter.py` |
| 팀원 E | `test_pipeline.py` 중심 통합 검증 |

공용 파일 변경이 필요하면 먼저 담당 Issue 댓글이나 팀 채널에 변경 이유를 알린다.

## 작업 흐름

1. 담당 Issue를 읽고 Assignee를 확인한다.
2. 최신 `main`에서 Issue 전용 브랜치를 만든다.
3. 작은 단위로 구현하고 테스트한다.
4. 커밋 메시지에 Issue 번호를 작성한다.
5. PR 본문에 구현 내용과 실행한 테스트를 적는다.
6. 팀장은 테스트 결과와 변경 내용을 확인하고, 필요한 리뷰 대화를 해결한 후 Squash merge한다. 팀원 승인은 권장하지만 필수는 아니다.

예시:

```bash
git switch main
git pull origin main
git switch -c feature/4-rss-collector
git add news_pipeline/collectors tests/test_collectors.py
git commit -m "feat: implement RSS collector (#4)"
git push -u origin feature/4-rss-collector
```

## 금지 사항

- `main`에 직접 push하지 않는다.
- `.env`, API 키, 개인 DB, 로그, 생성 리포트를 커밋하지 않는다.
- 다른 담당자의 공용 파일을 협의 없이 대규모 수정하지 않는다.
- 단위 테스트에서 실제 뉴스 사이트나 OpenAI API를 호출하지 않는다.
