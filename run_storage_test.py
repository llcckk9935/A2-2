from storage import NewsRepository


repo = NewsRepository("ai_news_storage_v1.db")

# 1. DB 초기화
repo.init_db()
print("1. DB 초기화 완료")


# 2. raw_news 저장 테스트
raw_id = repo.save_raw_news({
    "source": "test_source",
    "source_id": "RAW_TEST_001",
    "collection_method": "rss",
    "category": "AI",
    "title": "저장소 계층 테스트 뉴스",
    "url": "https://example.com/storage-test-001",
    "published_at_raw": "2026-08-24 10:00:00",
    "content_raw": "원본 뉴스 본문입니다.",
    "raw_payload": {
        "author": "테스트 작성자",
        "rss_title": "저장소 계층 테스트 뉴스"
    }
}, policy="upsert")

print("2. raw_news 저장 완료:", raw_id)


# 3. clean_news 저장 테스트
clean_id = repo.save_clean_news({
    "raw_id": raw_id,
    "source": "test_source",
    "category": "AI",
    "title": "저장소 계층 테스트 뉴스",
    "canonical_url": "https://example.com/storage-test-001",
    "published_at": "2026-08-24 10:00:00",
    "content": "정제된 뉴스 본문입니다.",
    "summary_status": "pending"
}, policy="upsert")

print("3. clean_news 저장 완료:", clean_id)


# 4. 미요약 뉴스 조회 테스트
unsummarized = repo.get_unsummarized_news(limit=5)
print("4. 미요약 뉴스 개수:", len(unsummarized))


# 5. AI 요약 결과 저장 테스트
repo.save_summary_result(clean_id, {
    "summary": "이 기사는 SQLite 저장소 계층을 테스트하기 위한 뉴스입니다.",
    "key_points": [
        "raw_news와 clean_news를 분리 저장한다.",
        "AI 요약 결과를 저장한다.",
        "ai_provider와 ai_model을 함께 저장한다."
    ],
    "ai_provider": "mock",
    "ai_model": "mock-summary-v1"
})

print("5. AI 요약 결과 저장 완료")


# 6. ID로 뉴스 조회 테스트
news = repo.get_news_by_id(clean_id)

print("6. 뉴스 조회 결과")
print("id:", news["id"])
print("title:", news["title"])
print("summary_status:", news["summary_status"])
print("ai_provider:", news["ai_provider"])
print("ai_model:", news["ai_model"])
print("key_points:", news["key_points"])


# 7. 분석 결과 저장 테스트
analysis_id = repo.save_analysis_result({
    "date_from": "2026-08-24",
    "date_to": "2026-08-24",
    "category": "AI",
    "article_count": 1,
    "trends": ["AI 뉴스 저장 자동화"],
    "keywords": ["AI", "SQLite", "저장소"],
    "major_issues": ["중복 뉴스 처리", "AI 모델 변경 호환성"],
    "common_points": ["뉴스 데이터를 영구 저장해야 한다."],
    "differences": ["AI 업체가 바뀌어도 DB 구조는 유지된다."],
    "implications": ["저장소 계층을 분리하면 유지보수가 쉬워진다."],
    "article_ids": [clean_id],
    "category_counts": {"AI": 1},
    "ai_provider": "mock",
    "ai_model": "mock-analysis-v1",
    "status": "success"
})

print("7. 분석 결과 저장 완료:", analysis_id)


# 8. 분석 결과 목록 조회 테스트
analysis_list = repo.list_analysis_results(limit=5)
print("8. 분석 결과 목록 개수:", len(analysis_list))


# 9. 뉴스 목록 조회 테스트
news_list = repo.list_news(limit=5)
print("9. 뉴스 목록 개수:", len(news_list))


# 10. 카테고리별 개수 조회 테스트
category_counts = repo.get_category_counts()
print("10. 카테고리별 개수:", category_counts)


# 11. 요약 상태별 개수 조회 테스트
status_counts = repo.get_summary_status_counts()
print("11. 요약 상태별 개수:", status_counts)


print("테스트 전체 완료")