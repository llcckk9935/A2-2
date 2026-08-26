from storage import NewsRepository


repo = NewsRepository("ai_news_storage_v1.db")


print("=== 저장소 조회 기능 테스트 시작 ===")


# 1. 분석 결과 목록 조회
analysis_list = repo.list_analysis_results(limit=5)

print("\n1. 분석 결과 목록")
print("개수:", len(analysis_list))

for item in analysis_list:
    print(item)


# 2. 분석 결과 상세 조회
if analysis_list:
    analysis_id = analysis_list[0]["id"]
    detail = repo.get_analysis_result(analysis_id)

    print("\n2. 분석 결과 상세 조회")
    print("id:", detail["id"])
    print("category:", detail["category"])
    print("article_count:", detail["article_count"])
    print("trends:", detail["trends"])
    print("keywords:", detail["keywords"])
    print("article_ids:", detail["article_ids"])
    print("ai_provider:", detail["ai_provider"])
    print("ai_model:", detail["ai_model"])
else:
    print("\n2. 분석 결과가 없어서 상세 조회를 건너뜁니다.")


# 3. 전체 뉴스 목록 조회
news_list = repo.list_news(limit=10)

print("\n3. 전체 뉴스 목록")
print("개수:", len(news_list))

for news in news_list:
    print({
        "id": news["id"],
        "title": news["title"],
        "category": news["category"],
        "summary_status": news["summary_status"],
    })


# 4. 카테고리 필터 조회
ai_news = repo.list_news(category="AI", limit=10)

print("\n4. AI 카테고리 뉴스 조회")
print("개수:", len(ai_news))

for news in ai_news:
    print(news["id"], news["title"])


# 5. 요약 완료 뉴스 조회
summarized_news = repo.list_news(summary_status="summarized", limit=10)

print("\n5. 요약 완료 뉴스 조회")
print("개수:", len(summarized_news))

for news in summarized_news:
    print(news["id"], news["title"], news["summary_status"])


# 6. 날짜 필터 조회
date_news = repo.list_news(
    date_from="2026-08-24 00:00:00",
    date_to="2026-08-24 23:59:59",
    limit=10
)

print("\n6. 날짜 필터 뉴스 조회")
print("개수:", len(date_news))

for news in date_news:
    print(news["id"], news["title"], news["published_at"])


# 7. 카테고리별 개수 집계
category_counts = repo.get_category_counts()

print("\n7. 카테고리별 뉴스 개수")
print(category_counts)


# 8. 요약 상태별 개수 집계
summary_status_counts = repo.get_summary_status_counts()

print("\n8. 요약 상태별 뉴스 개수")
print(summary_status_counts)


print("\n=== 저장소 조회 기능 테스트 완료 ===")