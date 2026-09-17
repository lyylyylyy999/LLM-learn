import time
import logging
from dataclasses import dataclass
from typing import Callable
from openai import OpenAI


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummarySettings:
    model: str
    max_output_tokens: int

    def __post_init__(self) -> None:
        if self.model.strip() == "":
            raise ValueError("model 不能是空字符串或者纯空白模型名")
        if self.max_output_tokens < 16:
            raise ValueError("max_output_tokens 不能小于 16")


@dataclass(frozen=True)
class SuccessResult:
    summary_text: str
    response_id: str
    response_model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    elapsed_seconds: float


class LLMError(Exception):
    pass


def llm_summary(
    client: OpenAI,
    text: str,
    summary_settings: SummarySettings,
    clock: Callable[[], float] = time.perf_counter,
) -> SuccessResult:
    if text.strip() == "":
        raise ValueError("拒绝空字符串或纯空白对话")
    start_time = clock()
    response = client.responses.create(
        model=summary_settings.model,
        instructions="摘要目标是获得 SuccessResult 数据结构，不添加原文不存在的信息",
        input=text,
        max_output_tokens=summary_settings.max_output_tokens,
        store=False,
    )
    if response.status == "completed" and response.output_text.strip() != "":
        summary_text = response.output_text
        end_time = clock()
        elapsed_seconds = end_time - start_time
        if response.usage is None:
            logger.info(
                "LLM summary succeeded: model=%s response_id=%s "
                "input_tokens=None output_tokens=None total_tokens=None elapsed_seconds=%.6f",
                response.model,
                response.id,
                elapsed_seconds,
            )
            return SuccessResult(
                summary_text=summary_text,
                response_id=response.id,
                response_model=response.model,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                elapsed_seconds=elapsed_seconds,
            )
        else:
            logger.info(
                "LLM summary succeeded: model=%s response_id=%s "
                "input_tokens=%d output_tokens=%d total_tokens=%d elapsed_seconds=%.6f",
                response.model,
                response.id,
                response.usage.input_tokens,
                response.usage.output_tokens,
                response.usage.total_tokens,
                elapsed_seconds,
            )
        return SuccessResult(
            summary_text=summary_text,
            response_id=response.id,
            response_model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            elapsed_seconds=elapsed_seconds,
        )
    else:
        logger.info(
            "LLM summary failed: status=%s response_id=%s",
            response.status,
            response.id,
        )
        raise LLMError(f"发生异常，响应 ID: {response.id},状态: {response.status}")


# client = OpenAI(
#     api_key=os.environ["DEEPSEEK_API_KEY"],
#     base_url="https://api.deepseek.com",
# )

# text = """ """

# settings = SummarySettings(
#     model="deepseek-flash",
#     max_output_tokens=2000,
# )

# result = llm_summary(
#     client=client,
#     text=text,
#     summary_settings=settings,
# )
# print(result)
