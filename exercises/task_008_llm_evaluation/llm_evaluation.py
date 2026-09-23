import json
import re
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)

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
    model_config = ConfigDict(extra="forbid")

    role: NonBlankStr
    content: NonBlankStr


class ExpectedContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankStr
    acceptable_phrases: list[NonBlankStr] = Field(min_length=1, max_length=3)


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: NonBlankStr
    conversation: list[Message] = Field(min_length=1)

    expected_summary: list[ExpectedContent]
    expected_key_points: list[ExpectedContent]
    expected_action_items: list[ExpectedContent]


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary_Expected_count: int
    key_points_Expected_count: int
    action_items_Expected_count: int
    summary_match_count: int
    key_points_match_count: int
    action_items_match_count: int
    summary_coverage: float | None
    key_points_coverage: float | None
    action_items_coverage: float | None
    no_action_items_correct: bool | None
    passed: bool


class EvaluationDataError(Exception):
    pass


def verify_evaluation_set(path: Path | str) -> list[EvalCase]:
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
                raise EvaluationDataError(f"第{line_number}行存在不合法 JSON") from exc
            except ValidationError:
                raise EvaluationDataError(f"第{line_number}行数据校验失败")
            if case.case_id in seen_case_ids:
                raise EvaluationDataError(f"在第{line_number}行 case_id 存在重复")
            seen_case_ids.add(case.case_id)
            cases.append(case)
    return cases


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def count_matched_concepts(
    output: str | list[str],
    concepts: list[ExpectedContent],
) -> int:
    if isinstance(output, list):
        output = " ".join(output)

    normalized_output = normalize_text(output)

    return sum(
        any(
            normalize_text(phrase) in normalized_output
            for phrase in concept.acceptable_phrases
        )
        for concept in concepts
    )


def evaluation(case: EvalCase, result: AnalysisResult) -> EvalResult:
    summary_Expected_count = len(case.expected_summary)
    key_points_Expected_count = len(case.expected_key_points)
    action_items_Expected_count = len(case.expected_action_items)
    summary_match_count = count_matched_concepts(
        result.summary,
        case.expected_summary,
    )
    key_points_match_count = count_matched_concepts(
        result.key_points,
        case.expected_key_points,
    )
    action_items_match_count = count_matched_concepts(
        result.action_items,
        case.expected_action_items,
    )

    summary_coverage = (
        summary_match_count / summary_Expected_count
        if len(case.expected_summary) != 0
        else None
    )
    key_points_coverage = (
        key_points_match_count / key_points_Expected_count
        if len(case.expected_key_points) != 0
        else None
    )
    action_items_coverage = (
        action_items_match_count / action_items_Expected_count
        if len(case.expected_action_items) != 0
        else None
    )

    if case.expected_action_items:
        no_action_items_correct = None
    else:
        no_action_items_correct = not result.action_items

    summary_passed = summary_coverage is None or summary_coverage == 1.0

    key_points_passed = key_points_coverage is None or key_points_coverage == 1.0

    if case.expected_action_items:
        action_items_passed = action_items_coverage == 1.0
    else:
        action_items_passed = no_action_items_correct is True

    passed = summary_passed and key_points_passed and action_items_passed

    return EvalResult(
        summary_Expected_count=summary_Expected_count,
        key_points_Expected_count=key_points_Expected_count,
        action_items_Expected_count=action_items_Expected_count,
        summary_match_count=summary_match_count,
        key_points_match_count=key_points_match_count,
        action_items_match_count=action_items_match_count,
        summary_coverage=summary_coverage,
        key_points_coverage=key_points_coverage,
        action_items_coverage=action_items_coverage,
        no_action_items_correct=no_action_items_correct,
        passed=passed,
    )
