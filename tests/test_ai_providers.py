import unittest

from news_pipeline.config import AIConfig
from news_pipeline.models import InsightResult, SummaryResult
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
