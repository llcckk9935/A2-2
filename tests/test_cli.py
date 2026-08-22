import argparse
import contextlib
import io
import unittest

from news_pipeline.cli import create_parser, validate_args


class CLITestCase(unittest.TestCase):
    def test_required_subcommands_are_registered(self):
        parser = create_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertEqual(
            set(subparsers.choices),
            {"fetch", "clean", "summarize", "analyze", "report", "export"},
        )

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
