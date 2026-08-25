"""테스트 공용 헬퍼. Issue #11에서 임시 프로젝트 환경을 준비한다.

실제 사용자 DB, 로그, 리포트를 건드리지 않도록 모든 테스트는 임시 디렉터리에서 실행한다.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any


VALID_CONFIG: dict[str, Any] = {
    "app": {"name": "A2-2 Test", "timezone": "Asia/Seoul"},
    "database": {"path": "data/news.db"},
    "news": {
        "default_source": "inews24",
        "default_limit": 20,
        "request_timeout_seconds": 10,
        "crawl_delay_seconds": 0,
        "user_agent": "A2-2-Test/1.0",
        "duplicate_policy": "skip",
        "categories": ["politics", "economy", "society", "it"],
        "sources": {
            "inews24": {
                "enabled": True,
                "base_url": "https://www.inews24.com",
                "rss_urls": {"it": "https://example.invalid/it.xml"},
            }
        },
    },
    "ai": {
        "provider": "mock",
        "api_key_env": "GEMINI_API_KEY",
        "model": "mock-model",
        "timeout_seconds": 30,
        "max_input_chars": 12000,
        "max_output_tokens": 500,
        "max_retries": 2,
        "retry_base_seconds": 1.0,
    },
    "report": {
        "default_top_n": 5,
        "chart_dpi": 100,
        "font_family": "auto",
        "output_directory": "reports",
    },
    "export": {"output_directory": "exports"},
    "logging": {
        "level": "INFO",
        "file": "logs/app.log",
        "max_bytes": 1048576,
        "backup_count": 1,
    },
}


def build_config(**overrides: Any) -> dict[str, Any]:
    """유효한 설정을 복사한 뒤 최상위 섹션만 덮어쓴다."""

    payload = copy.deepcopy(VALID_CONFIG)
    for section, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(section), dict):
            payload[section].update(value)
        else:
            payload[section] = value
    return payload


class TempProjectTestCase(unittest.TestCase):
    """임시 프로젝트 루트와 config.json을 준비하는 테스트 베이스."""

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temporary_directory.name)
        self.config_path = self.project_root / "config.json"
        self.write_config(VALID_CONFIG)
        self._saved_api_key = os.environ.pop("GEMINI_API_KEY", None)

    def tearDown(self) -> None:
        # Windows에서는 열린 로그 파일이 있으면 임시 디렉터리를 지울 수 없다.
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            handler.close()
        root_logger.handlers.clear()
        if self._saved_api_key is not None:
            os.environ["GEMINI_API_KEY"] = self._saved_api_key
        self._temporary_directory.cleanup()

    def write_config(self, payload: dict[str, Any] | str) -> Path:
        """설정 파일을 기록한다. 문자열을 주면 그대로 써서 문법 오류를 재현한다."""

        if isinstance(payload, str):
            self.config_path.write_text(payload, encoding="utf-8")
        else:
            self.config_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        return self.config_path

    def cli_args(self, *command: str) -> list[str]:
        return ["--config", str(self.config_path), *command]
