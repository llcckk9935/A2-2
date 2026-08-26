"""설정에 맞는 AI Provider를 생성한다."""

from news_pipeline.config import AIConfig
from news_pipeline.providers.base import AIProvider, ProviderConfigError
from news_pipeline.providers.mock_provider import MockAIProvider
from news_pipeline.providers.openai_provider import OpenAIProvider


def create_provider(name: str, config: AIConfig) -> AIProvider:
    if name == "openai":
        return OpenAIProvider(config)
    if name == "mock":
        return MockAIProvider(config)
    raise ProviderConfigError(f"지원하지 않는 AI Provider입니다: {name}")
