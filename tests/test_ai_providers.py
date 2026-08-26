import os
import sys
import types
import unittest
from unittest.mock import patch

from news_pipeline.config import AIConfig
from news_pipeline.models import InsightResult, SummaryResult
from news_pipeline.providers.gemini_provider import GeminiProvider
from news_pipeline.providers.mock_provider import MockAIProvider


class MockProviderTestCase(unittest.TestCase):
    def test_mock_summary_contains_news_title(self):
        provider = MockAIProvider(AIConfig())
        result = provider.generate_json(
            task="summary",
            prompt="테스트 프롬프트",
            response_schema=SummaryResult,
            metadata={"title": "AI 반도체 시장 경쟁 본격화"},
        )

        self.assertIn("AI 반도체 시장 경쟁 본격화", result["summary"])
        self.assertIn("[Mock]", result["summary"])
        self.assertEqual(len(result["key_points"]), 2)

    def test_mock_analysis_matches_schema(self):
        provider = MockAIProvider(AIConfig())
        result = provider.generate_json(
            task="analysis",
            prompt="테스트 프롬프트",
            response_schema=InsightResult,
            metadata={"category": "it", "article_count": 3},
        )

        validated = InsightResult.model_validate(result)
        self.assertTrue(validated.keywords)
        self.assertIn("3건", validated.major_issues[0])

    def test_gemini_client_uses_configured_timeout_in_milliseconds(self):
        captured = {}

        class FakeHttpOptions:
            def __init__(self, **kwargs):
                captured["http_options"] = kwargs

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.models = types.SimpleNamespace(
                    generate_content=lambda **_: types.SimpleNamespace(
                        text='{"summary":"요약","key_points":["핵심 1","핵심 2"]}'
                    )
                )

        fake_genai = types.SimpleNamespace(Client=FakeClient)
        fake_types = types.SimpleNamespace(
            HttpOptions=FakeHttpOptions,
            GenerateContentConfig=lambda **kwargs: kwargs,
        )
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai
        fake_google_genai = types.ModuleType("google.genai")
        fake_google_genai.types = fake_types
        provider = GeminiProvider(AIConfig(provider="gemini", timeout_seconds=12.5))
        with patch.dict(sys.modules, {"google": fake_google, "google.genai": fake_google_genai}):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                provider.generate_json("summary", "본문", SummaryResult)

        self.assertEqual(captured["http_options"]["timeout"], 12_500)