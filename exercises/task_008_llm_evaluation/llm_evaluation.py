import json
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, Field, StringConstraints, model_validator

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
    model_config = ConfigDict(extra="forbid")

    case_id: NonBlankStr
    conversation: list[Message] = Field(min_length=1)

    expected_summary: list[ExceptedContent]
    expected_key_points: list[ExceptedContent]
    expected_action_items: list[ExceptedContent]


class EvalResult(BaseModel):
    summary_excepted_count: int
    key_points_excepted_count: int
    action_items_excepted_count: int
    summary_match_count: int
    key_points_match_count: int
    action_items_match_count: int
    summary_coverage: float | None
    key_points_coverage: float | None
    action_items_coverage: float | None
    no_action_items_correct: bool | None
    passed: bool


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


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def count_matched_concepts(
    output: str | list[str],
    concepts: list[ExceptedContent],
) -> int:
    outputs = [output] if isinstance(output, str) else output
    normalized_outputs = [normalize_text(item) for item in outputs]

    return sum(
        any(
            normalize_text(phrase) in normalized_output
            for phrase in concept.acceptable_phrases
            for normalized_output in normalized_outputs
        )
        for concept in concepts
    )


def evaluation(case: EvalCase, result: AnalysisResult) -> EvalResult:
    summary_excepted_count = len(case.expected_summary)
    key_points_excepted_count = len(case.expected_key_points)
    action_items_excepted_count = len(case.expected_action_items)
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
 
    summary_coverage = summary_match_count / summary_excepted_count
    key_points_coverage = key_points_match_count / key_points_excepted_count
    action_items_coverage = action_items_match_count / action_items_excepted_count if len(case.expected_action_items) != 0 else None

    if case.expected_action_items == []:
        no_action_items_correct = True
    else:
        no_action_items_correct = None

    if summary_coverage == 1 and key_points_coverage == 1 and (action_items_coverage == 1 or action_items_coverage is None):
        passed = True
    else:
        passed = False

    return EvalResult(
        summary_excepted_count=summary_excepted_count,
        key_points_excepted_count=key_points_excepted_count,
        action_items_excepted_count=action_items_excepted_count,
        summary_match_count=summary_match_count,
        key_points_match_count=key_points_match_count,
        action_items_match_count=action_items_match_count,
        summary_coverage=summary_coverage,
        key_points_coverage=key_points_coverage,
        action_items_coverage=action_items_coverage,
        no_action_items_correct=no_action_items_correct,
        passed=passed,
    )


# cases = verify_evaluation_set("evals/task_008/cases.jsonl")
# result = AnalysisResult(
#     summary="减少全表扫描,占用额外存储空间",
#     key_points=["数据结构维护映射", "增加写入成本"],
#     action_items=["1"]
# )
# print(evaluation(cases[0], result))
