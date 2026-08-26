"""argparse 기반 CLI 정의와 공통 실행 준비."""

from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from news_pipeline.config import (
    AppConfig,
    ConfigError,
    ensure_runtime_directories,
    load_config,
    resolve_project_path,
)
from news_pipeline.database import initialize_database
from news_pipeline.logger import setup_logging


CATEGORIES = ("politics", "economy", "society", "it", "all")
CommandHandler = Callable[[argparse.Namespace, AppConfig, Path], int]


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 정수를 입력하세요.")
    return number


def non_negative_float(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("0 이상의 숫자를 입력하세요.")
    return number


def iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc
    return value


def lower_text(value: str) -> str:
    return value.lower()

def resolve_provider(args: argparse.Namespace, config: AppConfig) -> str:
    """CLI Provider 옵션을 설정 파일의 기본값보다 우선하여 반환한다."""

    cli_provider = getattr(args, "provider", None)
    if cli_provider is not None:
        return cli_provider
    return config.ai.provider


def execute_command(
    args: argparse.Namespace,
    config: AppConfig,
    project_root: Path,
    service_handler: CommandHandler,
) -> int:
    """CLI 인자를 기능 서비스 어댑터에 전달하고 종료 코드를 반환한다."""

    if hasattr(args, "provider"):
        args.provider = resolve_provider(args, config)

    return int(service_handler(args, config, project_root))


def _add_date_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date-from", type=iso_date)
    parser.add_argument("--date-to", type=iso_date)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="아이뉴스24 기반 AI 뉴스 수집·분석 파이프라인",
    )
    parser.add_argument("--config", default="config.json", help="설정 파일 경로")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="RSS 수집 또는 기사 본문 크롤링")
    fetch.add_argument("--method", choices=("rss", "crawl", "all"), default="all")
    fetch.add_argument("--source", default="inews24")
    fetch.add_argument("--category", type=lower_text, choices=CATEGORIES, default="all")
    fetch.add_argument("--limit", type=positive_int, default=20)
    fetch.add_argument("--date", type=iso_date)
    fetch.add_argument("--delay", type=non_negative_float)
    fetch.add_argument("--duplicate-policy", choices=("skip", "upsert"))
    fetch.set_defaults(handler=_run_fetch)

    clean = subparsers.add_parser("clean", help="raw 뉴스를 검증하고 정제")
    clean.add_argument("--all", action="store_true", help="이미 정제된 항목도 대상으로 선택")
    clean.add_argument("--limit", type=positive_int)
    clean.add_argument("--duplicate-policy", choices=("skip", "upsert"))
    clean.set_defaults(handler=_run_clean)

    summarize = subparsers.add_parser("summarize", help="뉴스 본문 AI 요약")
    summary_target = summarize.add_mutually_exclusive_group(required=True)
    summary_target.add_argument("--all", action="store_true")
    summary_target.add_argument("--id", type=positive_int, metavar="NEWS_ID")
    summary_target.add_argument("--unsummarized", action="store_true")
    summarize.add_argument("--limit", type=positive_int)
    summarize.add_argument("--force", action="store_true")
    summarize.add_argument("--provider", choices=("gemini", "mock"))
    summarize.set_defaults(handler=_run_summarize)

    analyze = subparsers.add_parser("analyze", help="기간·카테고리별 AI 인사이트 분석")
    _add_date_filters(analyze)
    analyze.add_argument("--category", type=lower_text, choices=CATEGORIES)
    analyze.add_argument("--limit", type=positive_int)
    analyze.add_argument("--provider", choices=("gemini", "mock"))
    analysis_query = analyze.add_mutually_exclusive_group()
    analysis_query.add_argument("--list-results", action="store_true")
    analysis_query.add_argument("--result-id", type=positive_int)
    analyze.set_defaults(handler=_run_analyze)

    report = subparsers.add_parser("report", help="차트와 종합 리포트 생성")
    _add_date_filters(report)
    report.add_argument("--category", type=lower_text, choices=CATEGORIES)
    report.add_argument("--top-n", type=positive_int, default=5)
    report.add_argument("--format", choices=("txt", "md"), default="md")
    report.add_argument("--output")
    report.set_defaults(handler=_run_report)

    export = subparsers.add_parser("export", help="정제 뉴스 파일 내보내기")
    export.add_argument("--format", choices=("csv", "jsonl", "xlsx"), required=True)
    export.add_argument(
        "--status",
        choices=("all", "summarized", "unsummarized"),
        default="all",
    )
    export.add_argument("--category", type=lower_text, choices=CATEGORIES)
    _add_date_filters(export)
    export.add_argument("--output")
    export.set_defaults(handler=_run_export)

    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if getattr(args, "date_from", None) and getattr(args, "date_to", None):
        if args.date_from > args.date_to:
            parser.error("--date-from은 --date-to보다 늦을 수 없습니다.")

    if args.command == "summarize":
        if args.id is not None and args.limit is not None:
            parser.error("--id와 --limit은 함께 사용할 수 없습니다.")
        if args.unsummarized and args.force:
            parser.error("--unsummarized와 --force는 함께 사용할 수 없습니다.")

    if args.command == "analyze" and (args.list_results or args.result_id):
        generation_values = (args.date_from, args.date_to, args.category, args.limit, args.provider)
        if any(value is not None for value in generation_values):
            parser.error("분석 결과 조회 옵션과 새 분석 생성 옵션을 함께 사용할 수 없습니다.")


def _feature_pending(
    args: argparse.Namespace,
    _config: AppConfig,
    _project_root: Path,
) -> int:
    logging.getLogger("cli").warning(
        "'%s' 기능의 골격만 준비되었습니다. 담당 Issue에서 구현하세요.",
        args.command,
    )
    return 1


def _run_fetch(
    args: argparse.Namespace,
    config: AppConfig,
    project_root: Path,
) -> int:
    from news_pipeline.collectors import ArticleCrawler, RSSCollector
    from news_pipeline.database import Database
    from news_pipeline.services.collection_service import CollectionService

    source_config = config.news.sources.get(args.source)
    if source_config is None or not source_config.enabled:
        print(f"[ERROR] 사용할 수 없는 뉴스 소스입니다: {args.source}")
        return 2

    database_path = resolve_project_path(project_root, config.database.path)
    rss_collector = RSSCollector(
        source=args.source,
        rss_urls=source_config.rss_urls,
        timeout=config.news.request_timeout_seconds,
        user_agent=config.news.user_agent,
    )
    article_crawler = ArticleCrawler(
        timeout=config.news.request_timeout_seconds,
        user_agent=config.news.user_agent,
        selectors=source_config.article_selectors.model_dump(),
        respect_robots_txt=source_config.respect_robots_txt,
    )
    stats = CollectionService(
        Database(database_path),
        rss_collector,
        article_crawler,
    ).fetch(
        method=args.method,
        category=args.category,
        limit=args.limit,
        delay=args.delay if args.delay is not None else config.news.crawl_delay_seconds,
        duplicate_policy=args.duplicate_policy or config.news.duplicate_policy,
        published_date=args.date,
    )
    print(
        "수집 완료: "
        f"요청={stats.requested_count}, 저장={stats.success_count}, "
        f"실패={stats.failure_count}, 중복={stats.duplicate_count}, "
        f"스킵={stats.skipped_count}"
    )
    return 0 if stats.failure_count == 0 else 2


def _run_clean(
    args: argparse.Namespace,
    config: AppConfig,
    project_root: Path,
) -> int:
    from news_pipeline.services.cleaning import CleaningService

    database_path = resolve_project_path(project_root, config.database.path)
    duplicate_policy = args.duplicate_policy or config.news.duplicate_policy
    stats = CleaningService(database_path).clean(
        include_cleaned=args.all,
        limit=args.limit,
        duplicate_policy=duplicate_policy,
    )
    print(
        "정제 완료: "
        f"대상={stats.requested_count}, 성공={stats.success_count}, "
        f"실패={stats.failure_count}, 중복={stats.duplicate_count}, "
        f"스킵={stats.skipped_count}"
    )
    return 0 if stats.failure_count == 0 else 2

def _run_report(
    args: argparse.Namespace,
    config: AppConfig,
    project_root: Path,
) -> int:
    from news_pipeline.services.reporter import ReporterService

    service = ReporterService()
    service.generate(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        top_n=args.top_n,
        output_format=args.format,
        output=args.output,
    )
    return 0

def _run_export(
    args: argparse.Namespace,
    config: AppConfig,
    project_root: Path,
) -> int:
    from news_pipeline.services.exporter import ExporterService

    service = ExporterService()
    service.export(
        output_format=args.format,
        status=args.status,
        category=args.category,
        date_from=args.date_from,
        date_to=args.date_to,
        output=args.output,
        config=config,
        project_root=project_root,
    )
    return 0

def _make_provider(args: argparse.Namespace, config: AppConfig):
    from news_pipeline.providers.factory import create_provider

    ai_config = config.ai.model_copy(update={"provider": args.provider})
    return create_provider(args.provider, ai_config), ai_config


def _run_summarize(args: argparse.Namespace, config: AppConfig, project_root: Path) -> int:
    from news_pipeline.services.summarizer import SummarizerService

    provider, ai_config = _make_provider(args, config)
    database_path = resolve_project_path(project_root, config.database.path)
    stats = SummarizerService(database_path, ai_config, provider).summarize(
        news_id=args.id, all_news=args.all, unsummarized=args.unsummarized, limit=args.limit, force=args.force
    )
    print(f"요약 완료: 요청={stats.requested_count}, 성공={stats.success_count}, 실패={stats.failure_count}, 스킵={stats.skipped_count}")
    return 0 if stats.failure_count == 0 else 2


def _run_analyze(args: argparse.Namespace, config: AppConfig, project_root: Path) -> int:
    from news_pipeline.providers.base import AIProviderError
    from news_pipeline.services.analyzer import AnalyzerService

    provider, ai_config = _make_provider(args, config)
    database_path = resolve_project_path(project_root, config.database.path)
    service = AnalyzerService(database_path, ai_config, config.analysis, provider)
    if args.list_results:
        for item in service.list_results():
            print(f"{item.id}: {item.date_from or '-'} ~ {item.date_to or '-'} | {item.category or 'all'} | {item.article_count}건 | {item.ai_provider}/{item.ai_model}")
        return 0
    if args.result_id:
        item = service.get_result(args.result_id)
        if item is None:
            print(f"[ERROR] 분석 결과 ID {args.result_id}를 찾을 수 없습니다.")
            return 2
        print(f"분석 결과 #{item.id} ({item.article_count}건)")
        for title, values in (("주요 트렌드", item.insights.trends), ("핵심 키워드", item.insights.keywords), ("주요 이슈", item.insights.major_issues), ("공통점", item.insights.common_points), ("차이점", item.insights.differences), ("시사점", item.insights.implications)):
            print(f"\n[{title}]")
            print("\n".join(f"- {value}" for value in values))
        return 0
    try:
        result = service.analyze(date_from=args.date_from, date_to=args.date_to, category=args.category, limit=args.limit)
    except AIProviderError as exc:
        logging.getLogger("cli").error("AI 인사이트 분석 실패: %s", exc)
        print(f"[ERROR] AI 인사이트 분석 실패: {exc}")
        return 2
    if result is None:
        print("[ERROR] 분석할 요약 뉴스가 없거나 최소 기사 수에 미달합니다.")
        return 2
    print(f"분석 저장 완료: ID={result.id}, 기사={result.article_count}건, provider={result.ai_provider}/{result.ai_model}")
    return 0


def run_cli(
    argv: Sequence[str] | None = None,
    command_handler: CommandHandler | None = None,
) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    try:
        config, project_root = load_config(args.config)
        ensure_runtime_directories(config, project_root)
        log_path = resolve_project_path(project_root, config.logging.file)
        setup_logging(config.logging, log_path)
        database_path = resolve_project_path(project_root, config.database.path)
        initialize_database(database_path)
    except ConfigError as exc:
        print(f"[ERROR] {exc}")
        return 3
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"[ERROR] 실행 환경 초기화 실패: {exc}")
        return 4

    selected_handler = command_handler or args.handler
    return execute_command(
        args,
        config,
        project_root,
        selected_handler,
    )
