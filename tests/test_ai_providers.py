import os
import unittest
from unittest.mock import Mock, patch

from news_pipeline.config import AIConfig
from news_pipeline.models import InsightResult, SummaryResult
from news_pipeline.providers.mock_provider import MockAIProvider
from news_pipeline.providers.openai_provider import OpenAIProvider


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

    def test_openai_client_uses_documented_chat_completions_endpoint(self):
        provider = OpenAIProvider(
            AIConfig(
                provider="openai",
                base_url="https://copa.codyssey.kr/v1",
                timeout_seconds=12.5,
            )
        )
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {
            "choices": [{"message": {"content": '{"summary":"요약","key_points":["핵심 1","핵심 2"]}'}}]
        }
        with patch("news_pipeline.providers.openai_provider.requests.post", return_value=fake_response) as post:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
                provider.generate_json("summary", "본문", SummaryResult)

        self.assertEqual(post.call_args.args[0], "https://copa.codyssey.kr/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["timeout"], 12.5)
        self.assertEqual(post.call_args.kwargs["json"]["model"], "gpt-5-mini")
        self.assertEqual(post.call_args.kwargs["json"]["messages"][1]["content"], "본문")
