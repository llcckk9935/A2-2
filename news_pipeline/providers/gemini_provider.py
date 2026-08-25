"""Gemini Provider 계약. 실제 SDK 호출은 Issue #7에서 구현한다."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from pydantic import BaseModel

from news_pipeline.config import AIConfig
from news_pipeline.providers.base import (
    AIProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class GeminiProvider(AIProvider):
    def __init__(self, config: AIConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

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
        del task, metadata
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise ProviderConfigError(
                f"{self.config.api_key_env} 환경변수가 없습니다. Gemini 모드에는 API 키가 필요합니다."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderConfigError("google-genai 패키지가 없습니다. requirements.txt를 설치하세요.") from exc

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(self.config.timeout_seconds * 1000)),
        )
        schema = response_schema.model_json_schema()
        for attempt in range(self.config.max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=schema,
                        max_output_tokens=self.config.max_output_tokens,
                    ),
                )
                text = getattr(response, "text", None)
                if not text:
                    raise ProviderResponseError("Gemini 응답 텍스트가 없거나 안전 정책으로 차단되었습니다.")
                return response_schema.model_validate(json.loads(text)).model_dump()
            except (ProviderResponseError, json.JSONDecodeError) as exc:
                raise ProviderResponseError(f"Gemini JSON 응답 검증 실패: {exc}") from exc
            except Exception as exc:
                message = str(exc)
                lowered = message.lower()
                if "401" in message or "403" in message or "api key" in lowered or "permission" in lowered:
                    raise ProviderAuthError("Gemini API 인증 또는 권한 오류") from exc
                is_rate_limited = "429" in message or "resource_exhausted" in lowered
                is_transient = is_rate_limited or "timeout" in lowered or "connection" in lowered or "500" in message or "503" in message
                if not is_transient:
                    raise ProviderUnavailableError(f"Gemini API 요청 실패: {message}") from exc
                if attempt >= self.config.max_retries:
                    error_type = ProviderRateLimitError if is_rate_limited else ProviderTimeoutError
                    raise error_type(f"Gemini 일시적 오류 재시도 소진: {message}") from exc
                delay = self.config.retry_base_seconds * (2**attempt)
                self.logger.warning("Gemini 요청 재시도 %s/%s, %.1f초 후 재시도", attempt + 1, self.config.max_retries, delay)
                time.sleep(delay)
