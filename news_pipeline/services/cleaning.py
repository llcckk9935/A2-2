"""뉴스 데이터 정제 및 중복 처리 서비스"""

from typing import Optional
import re
from urllib.parse import urlparse, urlunparse


def normalize_text(text: Optional[str]) -> str:
    """HTML 태그 제거 및 텍스트 정규화"""
    if not text:
        return ""
    # HTML 태그 제거
    clean = re.sub(r"<[^>]+>", "", text)
    # 불필요한 공백 정리
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_url(url: str) -> str:
    """마케팅 추적 파라미터(utm_, fbclid 등) 및 fragment 제거"""
    if not url:
        return ""
    parsed = urlparse(url)
    query_params = []
    if parsed.query:
        for param in parsed.query.split("&"):
            if not param.startswith(("utm_", "fbclid", "gclid", "NaPm", "hsCtaTracking")):
                query_params.append(param)
    new_query = "&".join(query_params)
    
    clean_parsed = parsed._replace(query=new_query, fragment="")
    return urlunparse(clean_parsed)


def clean_news_item(raw_data: dict) -> dict:
    """raw 뉴스 데이터를 받아 clean 뉴스 데이터로 변환"""
    title = normalize_text(raw_data.get("title"))
    content = normalize_text(raw_data.get("content_raw"))
    canonical_url = normalize_url(raw_data.get("url"))

    return {
        "raw_id": raw_data.get("id"),
        "source": raw_data.get("source"),
        "category": raw_data.get("category"),
        "title": title,
        "canonical_url": canonical_url,
        "published_at": raw_data.get("published_at_raw"),
        "content": content,
        "summary_status": "pending",
    }
