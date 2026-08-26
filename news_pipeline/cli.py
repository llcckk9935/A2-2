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
    fetch.set_defaults(handler=_feature_pending)

    clean = subparsers.add_parser("clean", help="raw 뉴스를 검증하고 정제")
    clean.add_argument("--all", action="store_true", help="이미 정제된 항목도 대상으로 선택")
    clean.add_argument("--limit", type=positive_int)
    clean.add_argument("--duplicate-policy", choices=("skip", "upsert"))
    clean.set_defaults(handler=_feature_pending)

    summarize = subparsers.add_parser("summarize", help="뉴스 본문 AI 요약")
    summary_target = summarize.add_mutually_exclusive_group(required=True)
    summary_target.add_argument("--all", action="store_true")
    summary_target.add_argument("--id", type=positive_int, metavar="NEWS_ID")
    summary_target.add_argument("--unsummarized", action="store_true")
    summarize.add_argument("--limit", type=positive_int)
    summarize.add_argument("--force", action="store_true")
    summarize.add_argument("--provider", choices=("gemini", "mock"))
    summarize.set_defaults(handler=_feature_pending)

    analyze = subparsers.add_parser("analyze", help="기간·카테고리별 AI 인사이트 분석")
    _add_date_filters(analyze)
    analyze.add_argument("--category", type=lower_text, choices=CATEGORIES)
    analyze.add_argument("--limit", type=positive_int)
    analyze.add_argument("--provider", choices=("gemini", "mock"))
    analysis_query = analyze.add_mutually_exclusive_group()
    analysis_query.add_argument("--list-results", action="store_true")
    analysis_query.add_argument("--result-id", type=positive_int)
    analyze.set_defaults(handler=_feature_pending)

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
    export.set_defaults(handler=_feature_pending)

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