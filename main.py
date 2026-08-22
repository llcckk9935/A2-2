"""A2-2 AI 뉴스 파이프라인 CLI 진입점."""

from __future__ import annotations

import sys

from news_pipeline.cli import run_cli


def _configure_utf8_console() -> None:
    """Windows와 macOS에서 한글 CLI 출력을 UTF-8로 통일한다."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    _configure_utf8_console()
    sys.exit(run_cli())
