"""config.json과 환경변수를 안전하게 읽고 검증한다."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # 패키지 설치 전 도움말·진단 실행을 위한 최소 대체 경로
    def _load_dotenv(dotenv_path: str | Path, override: bool = False) -> None:
        path = Path(dotenv_path)
        if not path.is_file():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and (override or key not in os.environ):
                os.environ[key] = value


class ConfigError(RuntimeError):
    """설정 파일이 없거나 올바르지 않을 때 발생한다."""


class AppInfoConfig(BaseModel):
    name: str
    timezone: str = "Asia/Seoul"


class DatabaseConfig(BaseModel):
    path: str = "data/news.db"


class ArticleSelectorsConfig(BaseModel):
    title: list[str] = Field(default_factory=lambda: ["h1"])
    content: list[str] = Field(default_factory=lambda: ["#articleBody", "article"])
    remove: list[str] = Field(
        default_factory=lambda: [
            "script",
            "style",
            "nav",
            "aside",
            ".advertisement",
            ".ad",
            ".reporter",
            ".related-news",
        ]
    )
    premium: list[str] = Field(
        default_factory=lambda: [".paywall", ".premium", "[data-premium='true']"]
    )


class NewsSourceConfig(BaseModel):
    enabled: bool = True
    base_url: str
    rss_urls: dict[str, str] = Field(default_factory=dict)
    respect_robots_txt: bool = True
    article_selectors: ArticleSelectorsConfig = Field(default_factory=ArticleSelectorsConfig)


class NewsConfig(BaseModel):
    default_source: str = "inews24"
    default_limit: int = Field(default=20, gt=0)
    request_timeout_seconds: float = Field(default=10, gt=0)
    crawl_delay_seconds: float = Field(default=1.5, ge=0)
    user_agent: str
    duplicate_policy: Literal["skip", "upsert"] = "skip"
    categories: list[str]
    sources: dict[str, NewsSourceConfig]


class AIConfig(BaseModel):
    provider: Literal["gemini", "mock"] = "mock"
    api_key_env: str = "GEMINI_API_KEY"
    model: str = "gemini-3.5-flash-lite"
    timeout_seconds: float = Field(default=30, gt=0)
    max_input_chars: int = Field(default=12000, gt=0)
    max_output_tokens: int = Field(default=500, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_base_seconds: float = Field(default=1.0, gt=0)


class ReportConfig(BaseModel):
    default_top_n: int = Field(default=5, gt=0)
    chart_dpi: int = Field(default=150, gt=0)
    font_family: str = "auto"
    output_directory: str = "reports"


class ExportConfig(BaseModel):
    output_directory: str = "exports"


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = "logs/app.log"
    max_bytes: int = Field(default=1_048_576, gt=0)
    backup_count: int = Field(default=3, ge=0)


class AppConfig(BaseModel):
    app: AppInfoConfig
    database: DatabaseConfig
    news: NewsConfig
    ai: AIConfig
    report: ReportConfig
    export: ExportConfig
    logging: LoggingConfig


def load_config(config_path: str | Path = "config.json") -> tuple[AppConfig, Path]:
    """설정을 읽고, 설정 파일이 위치한 프로젝트 루트와 함께 반환한다."""

    path = Path(config_path).expanduser().resolve()
    if not path.is_file():
        raise ConfigError(f"설정 파일을 찾을 수 없습니다: {path}")

    _load_dotenv(path.parent / ".env", override=False)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = AppConfig.model_validate(payload)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json 문법 오류: {exc}") from exc
    except ValidationError as exc:
        raise ConfigError(f"config.json 값 검증 실패:\n{exc}") from exc

    if config.news.default_source not in config.news.sources:
        raise ConfigError("news.default_source가 news.sources에 없습니다.")

    return config, path.parent


def resolve_project_path(project_root: Path, configured_path: str) -> Path:
    """상대 경로는 프로젝트 루트를 기준으로 안전하게 해석한다."""

    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else project_root / path


def ensure_runtime_directories(config: AppConfig, project_root: Path) -> None:
    """실행 중 생성되는 파일의 상위 디렉터리를 준비한다."""

    paths = (
        resolve_project_path(project_root, config.database.path).parent,
        resolve_project_path(project_root, config.logging.file).parent,
        resolve_project_path(project_root, config.report.output_directory),
        resolve_project_path(project_root, config.export.output_directory),
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
