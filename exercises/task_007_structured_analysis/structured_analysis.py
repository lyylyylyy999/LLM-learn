import time
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, Field
from openai import OpenAI
from typing import Callable


@dataclass(frozen=True)
class SummarySettings:
    model: str
    max_output_tokens: int

    def __post_init__(self) -> None:
        if self.model.strip() == "":
            raise ValueError("model 不能是空字符串或者纯空白模型名")
        if self.max_output_tokens < 16:
            raise ValueError("max_output_tokens 不能小于 16")


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=0)
    key_points: list[str] = Field(min_length=1, max_length=5)
    action_items: list[str] = Field(min_length=0, max_length=5)


class SuccessResult(BaseModel):
    response_id: str = Field(min_length=0)
    response_model: str
    input_tokens: int | None = Field(gt=0)
    output_tokens: int | None = Field(gt=0)
    total_tokens: int | None = Field(gt=0)
    elapsed_seconds: float


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
        instructions="",
        max_output_tokens=settings.max_output_tokens,
        model=settings.model,
        text={
            "format": {
                "type": "json_schema",
                "name": "analysis_result",
                "schema": AnalysisResult.model_json_schema(),
            }
        }
    )
    if response.status == "completed" and response.output_text.strip() != "":
        end = clock()
        elapsed_seconds = end - start
        result = AnalysisResult.model_validate_json(response.output_text)
        return result


from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

result = structured_analysis(
    client=client,
    input="什么是过拟合",
    settings=SummarySettings(model="deepseek-flash", max_output_tokens=1000),
)
print(result)