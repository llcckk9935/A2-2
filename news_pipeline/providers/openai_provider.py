"""OpenAI 호환 Chat Completions API를 requests로 호출하는 AI Provider."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests
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


class OpenAIProvider(AIProvider):
    def __init__(self, config: AIConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    @property
    def provider_name(self) -> str:
        return "openai"

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
        del metadata
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise ProviderConfigError(
                f"{self.config.api_key_env} 환경변수가 없습니다. "
                "OpenAI 호환 모드에는 API 키가 필요합니다."
            )
        if not self.config.base_url:
            raise ProviderConfigError("OpenAI 호환 API base_url 설정이 없습니다.")

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "반드시 유효한 JSON 객체만 출력하세요. Markdown 코드 블록이나 "
                        "설명 문장을 추가하지 마세요. 응답은 다음 JSON Schema를 따라야 합니다: "
                        + json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        for attempt in range(self.config.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
            except requests.Timeout as exc:
                if attempt >= self.config.max_retries:
                    raise ProviderTimeoutError("OpenAI 호환 API 타임아웃 재시도 소진") from exc
                self._wait_before_retry(attempt)
                continue
            except requests.ConnectionError as exc:
                if attempt >= self.config.max_retries:
                    raise ProviderTimeoutError("OpenAI 호환 API 연결 실패 재시도 소진") from exc
                self._wait_before_retry(attempt)
                continue

            if response.status_code in (401, 403):
                raise ProviderAuthError("OpenAI 호환 API 인증 또는 권한 오류")
            if response.status_code == 429:
                if attempt >= self.config.max_retries:
                    raise ProviderRateLimitError("OpenAI 호환 API 사용량 또는 요청 제한 재시도 소진")
                self._wait_before_retry(attempt)
                continue
            if response.status_code >= 500:
                if attempt >= self.config.max_retries:
                    raise ProviderUnavailableError(
                        f"OpenAI 호환 API 응답 오류(status={response.status_code})"
                    )
                self._wait_before_retry(attempt)
                continue
            if response.status_code >= 400:
                raise ProviderResponseError(
                    f"OpenAI 호환 API 요청 형식 또는 모델 설정 오류(status={response.status_code})"
                )

            try:
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not content:
                    raise ProviderResponseError(f"OpenAI {task} 응답 본문이 없습니다.")
                parsed = json.loads(content)
                return response_schema.model_validate(parsed).model_dump()
            except ProviderResponseError:
                raise
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ProviderResponseError("OpenAI 호환 API의 JSON 응답 검증 실패") from exc

        raise ProviderUnavailableError("OpenAI 호환 API 요청을 완료하지 못했습니다.")

    def _wait_before_retry(self, attempt: int) -> None:
        delay = self.config.retry_base_seconds * (2**attempt)
        self.logger.warning(
            "OpenAI 호환 API 요청 재시도 %s/%s, %.1f초 후 재시도",
            attempt + 1,
            self.config.max_retries,
            delay,
        )
        time.sleep(delay)
