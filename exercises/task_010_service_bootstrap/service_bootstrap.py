import os

import openai
from fastapi import FastAPI

from exercises.task_007_structured_analysis.structured_analysis import (
    AnalysisResponse,
    AnalysisSettings,
    structured_analysis,
)
from exercises.task_009_fastapi_analysis.fastapi_analysis import create_app


def create_api_app() -> FastAPI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key is None or not api_key.strip():
        raise ValueError("DEEPSEEK_API_KEY is required")

    model = os.getenv("DEEPSEEK_MODEL")
    if model is None or not model.strip():
        raise ValueError("DEEPSEEK_MODEL is required")
    try:
        deepseek_max_output_tokens = int(
            os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "2000")
        )
    except ValueError as exc:
        raise ValueError("DEEPSEEK_MAX_OUTPUT_TOKENS 必须是整数且不小于 16") from exc
    if deepseek_max_output_tokens < 16:
        raise ValueError("DEEPSEEK_MAX_OUTPUT_TOKENS 必须是整数且不小于 16")
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )
    settings = AnalysisSettings(
        model=model,
        max_output_tokens=deepseek_max_output_tokens,
    )

    def analyze_conversation(conversation: str) -> AnalysisResponse:
        return structured_analysis(
            client=client,
            input=conversation,
            settings=settings,
        )

    return create_app(analyze_conversation)
