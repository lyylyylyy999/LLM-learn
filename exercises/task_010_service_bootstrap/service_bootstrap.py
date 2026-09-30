import os

from fastapi import FastAPI
import openai

from exercises.task_007_structured_analysis.structured_analysis import AnalysisSettings, structured_analysis
from exercises.task_009_fastapi_analysis.fastapi_analysis import create_app


DEEPSEEK_MAX_OUTPUT_TOKENS = 2000


def create_api_app() -> FastAPI:
    api_key = os.environ["DEEPSEEK_API_KEY"]
    model = os.environ["DEEPSEEK_MODEL"]
    if not isinstance(DEEPSEEK_MAX_OUTPUT_TOKENS, int) or DEEPSEEK_MAX_OUTPUT_TOKENS < 16:
        raise ValueError("DEEPSEEK_MAX_OUTPUT_TOKENS 必须是整数且不小于 16")
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )
    settings = AnalysisSettings(
        model=model,
        max_output_tokens=DEEPSEEK_MAX_OUTPUT_TOKENS,
    )
    result = structured_analysis(
        client=client,
        input="",
        settings=settings,
    )
    return create_app(result)
