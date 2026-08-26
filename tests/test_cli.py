import argparse
import contextlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from news_pipeline.config import AIConfig, AnalysisConfig
from news_pipeline.providers.base import ProviderTimeoutError
from news_pipeline.cli import (
    create_parser,
    execute_command,
    resolve_provider,
    validate_args,
    _run_analyze,
)

COMMANDS = (
    "fetch",
    "clean",
    "summarize",
    "analyze",
    "report",
    "export",
)


class CLITestCase(unittest.TestCase):
    def test_required_subcommands_are_registered(self):
        parser = create_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertEqual(set(subparsers.choices), set(COMMANDS))

    def test_each_subcommand_help_exits_successfully(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as exit_info:
                        create_parser().parse_args([command, "--help"])

                self.assertEqual(exit_info.exception.code, 0)

    def test_category_is_case_insensitive(self):
        args = create_parser().parse_args(["fetch", "--category", "IT"])
        self.assertEqual(args.category, "it")

    def test_summary_targets_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                create_parser().parse_args(["summarize", "--all", "--id", "1"])

    def test_unsummarized_and_force_are_rejected(self):
        parser = create_parser()
        args = parser.parse_args(["summarize", "--unsummarized", "--force"])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validate_args(parser, args)

    def test_cli_provider_overrides_config_default(self):
        args = SimpleNamespace(provider="openai")
        config = SimpleNamespace(ai=SimpleNamespace(provider="mock"))

        self.assertEqual(resolve_provider(args, config), "openai")

    def test_config_provider_is_used_when_cli_option_is_missing(self):
        args = SimpleNamespace(provider=None)
        config = SimpleNamespace(ai=SimpleNamespace(provider="mock"))

        self.assertEqual(resolve_provider(args, config), "mock")

    def test_execute_command_passes_arguments_to_service_handler(self):
        args = SimpleNamespace(
            command="summarize",
            provider="openai",
            limit=10,
        )
        config = SimpleNamespace(ai=SimpleNamespace(provider="mock"))
        project_root = Path("project")
        service_handler = Mock(return_value=0)

        exit_code = execute_command(
            args,
            config,
            project_root,
            service_handler,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(args.provider, "openai")
        service_handler.assert_called_once_with(args, config, project_root)

    def test_supported_providers_are_accepted(self):
        for provider in ("openai", "mock"):
            with self.subTest(provider=provider):
                args = create_parser().parse_args(
                    [
                        "summarize",
                        "--unsummarized",
                        "--provider",
                        provider,
                    ]
                )
                self.assertEqual(args.provider, provider)

    def test_unknown_provider_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                create_parser().parse_args(
                    [
                        "summarize",
                        "--unsummarized",
                        "--provider",
                        "unknown",
                    ]
                )

        self.assertNotEqual(exit_info.exception.code, 0)
    def test_analyze_provider_error_returns_user_facing_failure_code(self):
        args = SimpleNamespace(
            provider="mock",
            list_results=False,
            result_id=None,
            date_from=None,
            date_to=None,
            category=None,
            limit=None,
        )
        config = SimpleNamespace(
            ai=AIConfig(provider="mock"),
            analysis=AnalysisConfig(),
            database=SimpleNamespace(path="data/news.db"),
        )
        with patch("news_pipeline.services.analyzer.AnalyzerService") as service_class:
            service_class.return_value.analyze.side_effect = ProviderTimeoutError("timeout")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = _run_analyze(args, config, Path("project"))

        self.assertEqual(exit_code, 2)
        self.assertIn("AI 인사이트 분석 실패", output.getvalue())
