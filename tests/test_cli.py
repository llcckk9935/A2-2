import argparse
import contextlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from news_pipeline.cli import (
    create_parser,
    execute_command,
    resolve_provider,
    validate_args,
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
        args = SimpleNamespace(provider="gemini")
        config = SimpleNamespace(ai=SimpleNamespace(provider="mock"))

        self.assertEqual(resolve_provider(args, config), "gemini")

    def test_config_provider_is_used_when_cli_option_is_missing(self):
        args = SimpleNamespace(provider=None)
        config = SimpleNamespace(ai=SimpleNamespace(provider="mock"))

        self.assertEqual(resolve_provider(args, config), "mock")

    def test_execute_command_passes_arguments_to_service_handler(self):
        args = SimpleNamespace(
            command="summarize",
            provider="gemini",
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
        self.assertEqual(args.provider, "gemini")
        service_handler.assert_called_once_with(args, config, project_root)

    def test_supported_providers_are_accepted(self):
        for provider in ("gemini", "mock"):
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