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


ANALYSIS_INPUT = """
学生：我理解过拟合就是模型在训练集上表现很好，但是到了新的数据上表现变差。

老师：对，这是最核心的现象。更准确地说，模型不仅学习了训练数据中的有效规律，还把训练样本里的噪声和偶然特征也学进去了。

学生：所以是不是模型越复杂，就越容易过拟合？

老师：通常模型复杂度越高，拟合训练数据的能力越强，因此过拟合风险会增加，但不能简单地说复杂模型一定会过拟合。数据量、正则化、训练方式等都会影响结果。

学生：那训练误差很低、验证误差很高，可以作为判断过拟合的信号吗？

老师：可以。如果随着训练继续进行，训练误差持续下降，但验证误差开始上升，这是很典型的过拟合现象。

学生：常见的处理方法包括增加数据、正则化和提前停止，对吗？

老师：对。还可以根据具体模型降低模型复杂度，或者做数据增强。关键目标不是让训练集表现最好，而是提高模型对未见数据的泛化能力。

学生：明白了。那我下一步准备做一个小实验，用一个容易过拟合的数据集训练模型，同时记录训练集和验证集的 loss 曲线。

老师：可以。你重点观察训练 loss 持续下降而验证 loss 开始上升的阶段，然后分别尝试 L2 正则化和 early stopping，比较它们对验证集表现的影响。

学生：好的，我会先完成基线模型，再加入 L2 正则化和 early stopping，并记录三组实验结果进行比较。
"""


@dataclass(frozen=True)
class SummarySettings:
    model: str
    max_output_tokens: int

    def __post_init__(self) -> None:
        if self.model.strip() == "":
            raise ValueError("model 不能是空字符串或者纯空白模型名")
        if self.max_output_tokens < 16:
            raise ValueError("max_output_tokens 不能小于 16")


class SuccessResult(BaseModel):
    response_id: str = Field(min_length=0)
    response_model: str
    input_tokens: int | None = Field(gt=0)
    output_tokens: int | None = Field(gt=0)
    total_tokens: int | None = Field(gt=0)
    elapsed_seconds: float


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
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_seconds: float


class LLMError(Exception):
    pass


class StructuredOutputError(Exception):
    pass


def structured_analysis(
    client: OpenAI,
    input: str,
    settings: SummarySettings,
    clock: Callable[[], float] = time.perf_counter,
) -> AnalysisResult:
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
            logger.info(
                "LLM structured analysis succeeded: model=%s response_id=%s "
                "input_tokens=%d output_tokens=%d total_tokens=%d elapsed_seconds=%.6f "
                "validation_success=True",
                response.model,
                response.id,
                input_tokens,
                output_tokens,
                total_tokens,
                elapsed_seconds,
            )
        except ValidationError as exc:
            logger.info(
                "LLM structured analysis succeeded: model=%s response_id=%s "
                "input_tokens=%d output_tokens=%d total_tokens=%d elapsed_seconds=%.6f "
                "validation_success=False",
                response.model,
                response.id,
                input_tokens,
                output_tokens,
                total_tokens,
                elapsed_seconds,
            )
            raise StructuredOutputError("大模型结构化输出失败") from exc
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


# from openai import OpenAI
# import os

# client = OpenAI(
#     api_key=os.environ["DEEPSEEK_API_KEY"],
#     base_url="https://api.deepseek.com",
# )

# result = structured_analysis(
#     client=client,
#     input=ANALYSIS_INPUT,
#     settings=SummarySettings(model="deepseek-flash", max_output_tokens=1000),
# )
# print(result)
