"""Gemini Provider 계약. 실제 SDK 호출은 Issue #7에서 구현한다."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from news_pipeline.config import AIConfig
from news_pipeline.providers.base import AIProvider


class GeminiProvider(AIProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.config.model

    def generate_json(
        self,
        task: str,
        prompt: str,
        response_schema: type[BaseModel],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del task, prompt, response_schema, metadata
        raise NotImplementedError("Issue #7에서 Gemini SDK 호출을 구현하세요.")
