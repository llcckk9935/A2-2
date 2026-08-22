"""콘솔과 회전 파일 로그를 한 곳에서 설정한다."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from news_pipeline.config import LoggingConfig


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(config: LoggingConfig, log_path: Path) -> None:
    """중복 핸들러 없이 애플리케이션 로깅을 초기화한다."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, config.level))

    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    rotating_file = RotatingFileHandler(
        log_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    rotating_file.setFormatter(formatter)

    root_logger.addHandler(console)
    root_logger.addHandler(rotating_file)
