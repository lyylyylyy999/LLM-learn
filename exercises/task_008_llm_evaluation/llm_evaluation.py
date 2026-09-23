import json
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ValidationError, Field, StringConstraints, model_validator

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult


NonBlankStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"\S",
    ),
]


class Message(BaseModel):
    role: NonBlankStr
    content: NonBlankStr


class ExceptedContent(BaseModel):
    name: NonBlankStr
    acceptable_phrases: list[NonBlankStr] = Field(min_length=1, max_length=3)


class EvalCase(BaseModel):
    case_id: NonBlankStr
    conversation: list[Message] = Field(min_length=1)

    expected_summary: list[ExceptedContent]
    expected_key_points: list[ExceptedContent]
    expected_action_items: list[ExceptedContent]


def verify_evaluation_set(path: Path) -> list[EvalCase]:
    path = Path(path)
    cases: list[EvalCase] = []
    seen_case_ids: set[str] = set()
    if not path.exists():
        raise FileNotFoundError("该文件不存在")
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line.strip() == "":
                continue
            try:
                raw = json.loads(line)
                case = EvalCase.model_validate(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第{line_number}行存在不合法 JSON") from exc
            except ValidationError as exc:
                raise ValueError(f"第{line_number}行数据校验失败")
            if case.case_id in seen_case_ids:
                raise ValueError(f"在第{line_number}行 case_id 存在重复")
            seen_case_ids.add(case.case_id)
            cases.append(case)
    return cases


FailureCategory = Literal[
    "api_error",
    "timeout",
    "invalid_response",
]


class SingleEvaluationRecord(BaseModel):
    case_id: str
    result: AnalysisResult | None = None
    failure_category: FailureCategory | None = None
    model_name: str
    prompt_version: str
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    total_tokens: int | None = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_result_or_failure(self) -> "SingleEvaluationRecord":
        if (self.result is None) == (self.failure_category is None):
            raise ValueError(
                "Exactly one of result or failure_category must be present"
            )
        return self


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def count_matched_concepts(output: str, case: EvalCase):
    normalized_output = normalize_text(output)
    return sum(
        any(
            normalize_text(phrase) in normalized_output
            for phrase in concept.acceptable_phrases
        )
        for concept in case
    )


def evaluation(case: EvalCase, result: AnalysisResult) -> tuple[float, float, float | None]:
    match_summary = count_matched_concepts(
        result.summary,
        case.expected_summary,
    )
    match_key_points = count_matched_concepts(
        result.key_points,
        case.expected_key_points,
    )
    match_action_items = count_matched_concepts(
        result.action_items,
        case.expected_action_items,
    )

    coverage_summary = match_summary / len(case.expected_summary)
    coverage_key_points = match_key_points / len(case.expected_key_points)
    coverage_action_items = match_action_items / len(case.expected_action_items) if len(case.expected_action_items) else None

    return coverage_summary, coverage_key_points, coverage_action_items


class EvaluationReport(BaseModel):
    dataset_version: str
    model: str
    prompt_version: str
    total_case: int
    success_rate_case: float
    pass_rate_case: float