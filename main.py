import argparse
import html
import json
import logging
import re
import sqlite3
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


DB_PATH = Path("ai_news_storage_v1.db")
CONFIG_PATH = Path("config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s"
)

logger = logging.getLogger("cleaning")


DEFAULT_REQUIRED_FIELDS = [
    "source",
    "collection_method",
    "category",
    "title",
    "url",
    "collected_at",
]


TRACKING_PARAMS_PREFIX = (
    "utm_",
)

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def load_config():
    if not CONFIG_PATH.exists():
        return {
            "cleaning": {
                "duplicate_policy": "upsert",
                "required_fields": DEFAULT_REQUIRED_FIELDS,
                "remove_tracking_params": True,
            }
        }

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def empty_to_none(value):
    if value is None:
        return None

    if isinstance(value, str) and value.strip() == "":
        return None

    return value


def normalize_text(value):
    if value is None:
        return None

    text = str(value)

    # Unicode 정규화
    text = unicodedata.normalize("NFC", text)

    # HTML 엔티티 변환
    text = html.unescape(text)

    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", text)

    # 흔한 광고/안내 문구 제거
    remove_patterns = [
        r"무단전재\s*및\s*재배포\s*금지",
        r"저작권자.*?무단.*?금지",
        r"기자\s*메일.*",
        r"구독.*?알림.*",
        r"광고",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # 공백/줄바꿈 정리
    text = re.sub(r"\s+", " ", text).strip()

    return empty_to_none(text)


def normalize_url(url, remove_tracking_params=True):
    if not url:
        return None

    url = url.strip()
    parsed = urlsplit(url)

    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()

    query_items = []

    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        key_lower = key.lower()

        if remove_tracking_params:
            if key_lower.startswith(TRACKING_PARAMS_PREFIX):
                continue
            if key_lower in TRACKING_PARAMS:
                continue

        query_items.append((key, value))

    query = urlencode(query_items, doseq=True)

    path = parsed.path

    # 마지막 슬래시 정리
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # fragment 제거
    return urlunsplit((scheme, netloc, path, query, ""))


def parse_date(value):
    if value is None or str(value).strip() == "":
        return None

    raw = str(value).strip()

    # ISO 형식 먼저 시도
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return normalize_datetime(dt)
    except Exception:
        pass

    # RSS 날짜 형식 시도
    try:
        dt = parsedate_to_datetime(raw)
        return normalize_datetime(dt)
    except Exception:
        logger.warning("날짜 파싱 실패: %s", raw)
        return None


def normalize_datetime(dt):
    if ZoneInfo is None:
        return dt.isoformat(timespec="seconds")

    seoul = ZoneInfo("Asia/Seoul")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=seoul)
    else:
        dt = dt.astimezone(seoul)

    return dt.isoformat(timespec="seconds")


def validate_required_fields(row, required_fields):
    missing = []

    for field in required_fields:
        if field not in row.keys() or empty_to_none(row[field]) is None:
            missing.append(field)

    return missing


def get_raw_news(conn, limit=None):
    sql = """
        SELECT
            id,
            source,
            source_id,
            collection_method,
            category,
            title,
            url,
            published_at_raw,
            content_raw,
            raw_payload,
            collected_at,
            created_at,
            updated_at
        FROM raw_news
        ORDER BY id ASC
    """

    params = []

    if limit:
        sql += " LIMIT ?"
        params.append(limit)

    return conn.execute(sql, params).fetchall()


def get_existing_clean(conn, canonical_url):
    return conn.execute(
        """
        SELECT *
        FROM clean_news
        WHERE canonical_url = ?
        """,
        (canonical_url,)
    ).fetchone()


def choose_better_content(old_content, new_content):
    old_content = empty_to_none(old_content)
    new_content = empty_to_none(new_content)

    if old_content and new_content:
        return new_content if len(new_content) > len(old_content) else old_content

    return new_content or old_content


def save_clean_news(conn, clean_data, duplicate_policy):
    existing = get_existing_clean(conn, clean_data["canonical_url"])

    if existing and duplicate_policy == "skip":
        logger.info("중복 skip: %s", clean_data["canonical_url"])
        return "skipped"

    now = now_iso()

    if existing and duplicate_policy == "upsert":
        final_content = choose_better_content(existing["content"], clean_data["content"])

        summary_status = existing["summary_status"]

        # 이미 요약된 뉴스인데 본문이 더 좋아졌으면 재요약 필요 상태로 변경
        if (
            existing["summary_status"] == "summarized"
            and final_content
            and final_content != existing["content"]
        ):
            summary_status = "pending"

        # 빈 값으로 기존 값을 덮어쓰지 않기
        title = clean_data["title"] or existing["title"]
        category = clean_data["category"] or existing["category"]
        published_at = clean_data["published_at"] or existing["published_at"]

        conn.execute(
            """
            UPDATE clean_news
            SET
                raw_id = ?,
                source = ?,
                category = ?,
                title = ?,
                published_at = ?,
                content = ?,
                summary_status = ?,
                updated_at = ?
            WHERE canonical_url = ?
            """,
            (
                clean_data["raw_id"],
                clean_data["source"] or existing["source"],
                category,
                title,
                published_at,
                final_content,
                summary_status,
                now,
                clean_data["canonical_url"],
            )
        )

        logger.info("중복 upsert 갱신: %s", clean_data["canonical_url"])
        return "upserted"

    conn.execute(
        """
        INSERT INTO clean_news (
            raw_id,
            source,
            category,
            title,
            canonical_url,
            published_at,
            content,
            summary,
            key_points,
            summary_status,
            summarized_at,
            ai_provider,
            ai_model,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_data["raw_id"],
            clean_data["source"],
            clean_data["category"],
            clean_data["title"],
            clean_data["canonical_url"],
            clean_data["published_at"],
            clean_data["content"],
            None,
            json.dumps([], ensure_ascii=False),
            clean_data["summary_status"],
            None,
            None,
            None,
            now,
            now,
        )
    )

    logger.info("clean_news 저장: %s", clean_data["canonical_url"])
    return "inserted"


def clean_command(args):
    if not DB_PATH.exists():
        logger.error("DB 파일을 찾을 수 없습니다: %s", DB_PATH)
        return

    config = load_config()
    cleaning_config = config.get("cleaning", {})

    duplicate_policy = (
        args.duplicate_policy
        or cleaning_config.get("duplicate_policy")
        or "upsert"
    )

    required_fields = cleaning_config.get(
        "required_fields",
        DEFAULT_REQUIRED_FIELDS
    )

    remove_tracking_params = cleaning_config.get(
        "remove_tracking_params",
        True
    )

    limit = args.limit

    logger.info("정제 시작")
    logger.info("중복 정책: %s", duplicate_policy)

    success_count = 0
    failure_count = 0
    skipped_count = 0
    upserted_count = 0

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            raw_items = get_raw_news(conn, limit=limit)

            for row in raw_items:
                missing = validate_required_fields(row, required_fields)

                if missing:
                    logger.warning(
                        "필수 필드 누락으로 정제 제외 raw_id=%s missing=%s",
                        row["id"],
                        missing
                    )
                    failure_count += 1
                    continue

                title = normalize_text(row["title"])
                content = normalize_text(row["content_raw"])
                canonical_url = normalize_url(
                    row["url"],
                    remove_tracking_params=remove_tracking_params
                )
                published_at = parse_date(row["published_at_raw"])

                if not canonical_url:
                    logger.warning("URL 정규화 실패 raw_id=%s", row["id"])
                    failure_count += 1
                    continue

                if not content:
                    summary_status = "not_ready"
                    logger.warning(
                        "본문 없음: AI 요약 불가 상태로 저장 raw_id=%s",
                        row["id"]
                    )
                else:
                    summary_status = "pending"

                clean_data = {
                    "raw_id": row["id"],
                    "source": normalize_text(row["source"]),
                    "category": normalize_text(row["category"]),
                    "title": title,
                    "canonical_url": canonical_url,
                    "published_at": published_at,
                    "content": content,
                    "summary_status": summary_status,
                }

                result = save_clean_news(conn, clean_data, duplicate_policy)

                if result == "skipped":
                    skipped_count += 1
                elif result == "upserted":
                    upserted_count += 1
                    success_count += 1
                else:
                    success_count += 1

            conn.commit()

    except sqlite3.Error as e:
        logger.error("데이터베이스 오류: %s", e)
        return

    logger.info(
        "정제 완료 success=%s failure=%s skipped=%s upserted=%s",
        success_count,
        failure_count,
        skipped_count,
        upserted_count,
    )


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command")

    clean_parser = subparsers.add_parser("clean")
    clean_parser.add_argument("--all", action="store_true")
    clean_parser.add_argument("--limit", type=int)
    clean_parser.add_argument(
        "--duplicate-policy",
        choices=["skip", "upsert"],
        default=None
    )

    args = parser.parse_args()

    if args.command == "clean":
        clean_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()