from news_pipeline.services.cleaning import normalize_text, normalize_url


def test_normalize_text():
    html_text = "<p>  안녕하세요!   <b>뉴스</b>입니다. </p>"
    assert normalize_text(html_text) == "안녕하세요! 뉴스입니다."


def test_normalize_url():
    tracking_url = "https://example.com/news?utm_source=naver&fbclid=12345&id=7"
    canonical = normalize_url(tracking_url)
    assert "utm_source" not in canonical
    assert "fbclid" not in canonical
    assert canonical == "https://example.com/news?id=7"
