"""Issue #11 실패 시나리오 테스트.

한 건의 실패가 전체 프로그램을 예상치 못한 방식으로 중단시키지 않고,
정해진 종료 코드와 메시지로 처리되는지 검증한다.
네트워크와 Gemini API는 호출하지 않는다.
"""

from __future__ import annotations

import contextlib
import io
import unittest

from news_pipeline.cli import create_parser, run_cli, validate_args
from tests.support import TempProjectTestCase, build_config


CONFIG_ERROR_EXIT_CODE = 3
RUNTIME_ERROR_EXIT_CODE = 4


class ConfigFailureTestCase(TempProjectTestCase):
    """설정 파일 오류가 예외 전파 없이 종료 코드로 처리되는지 확인한다."""

    def run_fetch(self) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = run_cli(self.cli_args("fetch", "--limit", "1"))
        return exit_code, buffer.getvalue()

    def test_missing_config_file_is_reported(self):
        self.config_path.unlink()

        exit_code, output = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)
        self.assertIn("[ERROR]", output)

    def test_malformed_json_is_reported(self):
        self.write_config('{"app": {"name": "broken"')

        exit_code, output = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)
        self.assertIn("[ERROR]", output)

    def test_missing_required_section_is_reported(self):
        payload = build_config()
        del payload["database"]
        self.write_config(payload)

        exit_code, _ = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)

    def test_out_of_range_value_is_rejected(self):
        self.write_config(build_config(news={"default_limit": 0}))

        exit_code, _ = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)

    def test_unknown_duplicate_policy_is_rejected(self):
        self.write_config(build_config(news={"duplicate_policy": "overwrite"}))

        exit_code, _ = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)

    def test_default_source_must_exist_in_sources(self):
        self.write_config(build_config(news={"default_source": "unknown_press"}))

        exit_code, _ = self.run_fetch()

        self.assertEqual(exit_code, CONFIG_ERROR_EXIT_CODE)

    def test_output_directory_creation_failure_is_reported(self):
        blocking_file = self.project_root / "reports"
        blocking_file.write_text("이 경로는 디렉터리가 아니다.", encoding="utf-8")

        exit_code, output = self.run_fetch()

        self.assertEqual(exit_code, RUNTIME_ERROR_EXIT_CODE)
        self.assertIn("[ERROR]", output)

    def test_pipeline_starts_without_gemini_api_key(self):
        """API 키가 없어도 설정 초기화 단계는 통과해야 한다."""

        exit_code, _ = self.run_fetch()

        self.assertNotIn(exit_code, (CONFIG_ERROR_EXIT_CODE, RUNTIME_ERROR_EXIT_CODE))


class InvalidCLIOptionTestCase(unittest.TestCase):
    """잘못된 CLI 입력이 argparse 단계에서 걸러지는지 확인한다."""

    def assert_parse_fails(self, argv: list[str]) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                create_parser().parse_args(argv)
        self.assertNotEqual(exit_info.exception.code, 0)

    def test_unknown_subcommand_is_rejected(self):
        self.assert_parse_fails(["crawl-everything"])

    def test_missing_subcommand_is_rejected(self):
        self.assert_parse_fails([])

    def test_zero_limit_is_rejected(self):
        self.assert_parse_fails(["fetch", "--limit", "0"])

    def test_negative_limit_is_rejected(self):
        self.assert_parse_fails(["fetch", "--limit", "-5"])

    def test_negative_delay_is_rejected(self):
        self.assert_parse_fails(["fetch", "--delay", "-1"])

    def test_invalid_date_format_is_rejected(self):
        self.assert_parse_fails(["fetch", "--date", "2026/08/26"])

    def test_impossible_date_is_rejected(self):
        self.assert_parse_fails(["fetch", "--date", "2026-02-30"])

    def test_unknown_category_is_rejected(self):
        self.assert_parse_fails(["fetch", "--category", "sports"])

    def test_unknown_fetch_method_is_rejected(self):
        self.assert_parse_fails(["fetch", "--method", "selenium"])

    def test_export_format_is_required(self):
        self.assert_parse_fails(["export"])

    def test_unknown_export_format_is_rejected(self):
        self.assert_parse_fails(["export", "--format", "pdf"])

    def test_unknown_export_status_is_rejected(self):
        self.assert_parse_fails(["export", "--format", "csv", "--status", "failed"])

    def test_reversed_date_range_is_rejected(self):
        parser = create_parser()
        args = parser.parse_args(
            ["export", "--format", "csv", "--date-from", "2026-08-26", "--date-to", "2026-08-20"]
        )
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                validate_args(parser, args)
        self.assertNotEqual(exit_info.exception.code, 0)

    def test_analysis_query_and_generation_options_conflict(self):
        parser = create_parser()
        args = parser.parse_args(["analyze", "--list-results", "--category", "it"])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                validate_args(parser, args)
        self.assertNotEqual(exit_info.exception.code, 0)

    def test_summarize_id_and_limit_conflict(self):
        parser = create_parser()
        args = parser.parse_args(["summarize", "--id", "3", "--limit", "10"])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                validate_args(parser, args)
        self.assertNotEqual(exit_info.exception.code, 0)
