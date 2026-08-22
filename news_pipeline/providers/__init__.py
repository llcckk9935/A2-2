"""AI Provider 생성 함수."""

from __future__ import annotations

from news_pipeline.config import AIConfig
from news_pipeline.providers.base import AIProvider, ProviderConfigError
from news_pipeline.providers.gemini_provider import GeminiProvider
from news_pipeline.providers.mock_provider import MockAIProvider


def create_provider(provider_name: str, config: AIConfig) -> AIProvider:
    if provider_name == "mock":
        return MockAIProvider(config)
    if provider_name == "gemini":
        return GeminiProvider(config)
    raise ProviderConfigError(f"지원하지 않는 AI Provider입니다: {provider_name}")


__all__ = ["AIProvider", "GeminiProvider", "MockAIProvider", "create_provider"]
