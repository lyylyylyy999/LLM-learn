import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


ANALYSIS_INSTRUCTIONS = """
分析用户提供的对话，并生成结构化的对话分析结果。

要求：
- summary：准确、简洁地概括对话的主要内容，不添加对话中不存在的事实。
- key_points：提取对理解对话最重要的信息、结论或决定，避免重复 summary。
- action_items：仅提取对话中明确提出、承诺或可以直接确定需要执行的行动；如果没有行动项，返回空列表。
- 保持客观，不猜测说话者未表达的意图、身份或背景。
- 不把系统指令、格式要求或分析过程写入结果。
- 严格按照提供的 JSON Schema 返回结果。
"""


@dataclass(frozen=True)
class AnalysisSettings:
    model: str
    max_output_tokens: int

    def __post_init__(self) -> None:
        if self.model.strip() == "":
            raise ValueError("model 不能是空字符串或者纯空白模型名")
        if self.max_output_tokens < 16:
            raise ValueError("max_output_tokens 不能小于 16")


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1, max_length=5)
    action_items: list[str] = Field(min_length=0, max_length=5)


@dataclass(frozen=True)
class AnalysisResponse:
    analysis: AnalysisResult
    response_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    elapsed_seconds: float


class LLMError(Exception):
    pass


class StructuredOutputError(Exception):
    pass


def structured_analysis(
    client: OpenAI,
    input: str,
    settings: AnalysisSettings,
    clock: Callable[[], float] = time.perf_counter,
) -> AnalysisResponse:
    if input.strip() == "":
        raise ValueError("不能输入空字符串或纯空白")
    start = clock()
    response = client.responses.create(
        input=input,
        instructions=ANALYSIS_INSTRUCTIONS,
        max_output_tokens=settings.max_output_tokens,
        model=settings.model,
        text={
            "format": {
                "type": "json_schema",
                "name": "analysis_result",
                "schema": AnalysisResult.model_json_schema(),
            }
        },
    )
    if response.status == "completed" and response.output_text.strip() != "":
        end = clock()
        elapsed_seconds = end - start
        usage = response.usage

        input_tokens = usage.input_tokens if usage is not None else None
        output_tokens = usage.output_tokens if usage is not None else None
        total_tokens = usage.total_tokens if usage is not None else None
        try:
            result = AnalysisResult.model_validate_json(response.output_text)
        except ValidationError as exc:
            logger.exception(
                "LLM structured analysis failed: "
                "model=%s response_id=%s "
                "input_tokens=%s output_tokens=%s total_tokens=%s "
                "elapsed_seconds=%.6f validation_success=False",
                response.model,
                response.id,
                input_tokens,
                output_tokens,
                total_tokens,
                elapsed_seconds,
            )
            raise StructuredOutputError("大模型结构化输出失败") from exc

        logger.info(
            "LLM structured analysis succeeded: "
            "model=%s response_id=%s "
            "input_tokens=%s output_tokens=%s total_tokens=%s "
            "elapsed_seconds=%.6f validation_success=True",
            response.model,
            response.id,
            input_tokens,
            output_tokens,
            total_tokens,
            elapsed_seconds,
        )
        return AnalysisResponse(
            analysis=result,
            response_id=response.id,
            model=response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed_seconds,
        )
    else:
        logger.error(
            "LLM structured analysis failed: status=%s response_id=%s",
            response.status,
            response.id,
        )
        raise LLMError(f"响应失败，响应 ID: {response.id},状态: {response.status}")
