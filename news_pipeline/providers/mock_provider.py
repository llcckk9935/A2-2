"""네트워크와 API 키 없이 사용하는 결정적 테스트 Provider."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from news_pipeline.config import AIConfig
from news_pipeline.providers.base import AIProvider, ProviderConfigError


class MockAIProvider(AIProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_json(
        self,
        task: str,
        prompt: str,
        response_schema: type[BaseModel],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del prompt
        metadata = metadata or {}

        if task == "summary":
            title = str(metadata.get("title") or "제목 없음")
            result = {
                "summary": (
                    f"[Mock] '{title}' 기사에 대한 테스트용 요약입니다. "
                    "이 결과는 실제 Gemini API가 생성한 내용이 아닙니다."
                ),
                "key_points": [
                    f"[Mock] 대상 기사: {title}",
                    "[Mock] 요약 저장 흐름 확인용 핵심 내용",
                ],
            }
        elif task == "analysis":
            category = str(metadata.get("category") or "all")
            article_count = int(metadata.get("article_count") or 0)
            result = {
                "trends": [f"[Mock] {category} 카테고리의 테스트용 트렌드"],
                "keywords": ["Mock", category, "뉴스 분석"],
                "major_issues": [f"[Mock] 분석 대상 기사 수: {article_count}건"],
                "common_points": ["[Mock] 기사들의 공통점 테스트 결과"],
                "differences": ["[Mock] 기사들의 차이점 테스트 결과"],
                "implications": ["[Mock] 리포트 생성 확인용 시사점"],
            }
        else:
            raise ProviderConfigError(f"지원하지 않는 Mock 작업입니다: {task}")

        validated = response_schema.model_validate(result)
        return validated.model_dump()
