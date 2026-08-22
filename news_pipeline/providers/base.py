"""Gemini와 Mock이 함께 지키는 공통 계약과 예외."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class AIProviderError(Exception):
    pass


class ProviderConfigError(AIProviderError):
    pass


class ProviderAuthError(AIProviderError):
    pass


class ProviderTimeoutError(AIProviderError):
    pass


class ProviderRateLimitError(AIProviderError):
    pass


class ProviderUnavailableError(AIProviderError):
    pass


class ProviderResponseError(AIProviderError):
    pass


class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate_json(
        self,
        task: str,
        prompt: str,
        response_schema: type[BaseModel],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass
