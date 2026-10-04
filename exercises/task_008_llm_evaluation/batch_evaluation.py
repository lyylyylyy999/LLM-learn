from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, model_validator

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.llm_evaluation import (
    EvalCase,
    EvalResult,
    evaluation,
)


class BatchEvalResult(BaseModel):
    case_id: str
    status: Literal["scored", "failed"]
    score: EvalResult | None

    @model_validator(mode="after")
    def validate_status_and_score(self) -> "BatchEvalResult":
        if self.status == "scored" and self.score is None:
            raise ValueError("scored 结果一定包含 score")
        if self.status == "failed" and self.score is not None:
            raise ValueError("failed 结果一定不包含 score")

        return self


class BatchEvalReport(BaseModel):
    total_cases: int
    scored_cases: int
    failed_cases: int
    passed_cases: int
    pass_rate: float | None
    case_results: list[BatchEvalResult]

    @model_validator(mode="after")
    def validate_result_conservation(self) -> "BatchEvalReport":
        if (
            self.scored_cases + self.failed_cases != self.total_cases
            or self.passed_cases > self.scored_cases
            or len(self.case_results) != self.total_cases
        ):
            raise ValueError("评测报告结果不守恒")

        return self


def evaluate_batch(
    cases: Sequence[EvalCase], outcomes: Mapping[str, AnalysisResult | None]
):
    unique_cases = list({case.case_id: case for case in cases}.values())
    if len(cases) != len(unique_cases):
        raise ValueError("cases 中存在重复的 case_id")
    if len(cases) != len(outcomes):
        raise ValueError("存在缺失或多余 ID")
    for case in cases:
        if case.case_id not in outcomes.keys():
            raise ValueError("存在缺失或多余 ID")
    if len(cases) == len(outcomes) == 0:
        return BatchEvalReport(
            total_cases=0,
            scored_cases=0,
            failed_cases=0,
            passed_cases=0,
            pass_rate=None,
            case_results=[],
        )
    total_cases: int = len(cases)
    scored_cases: int = 0
    failed_cases: int = 0
    passed_cases: int = 0
    case_results: list[BatchEvalResult] = []
    for case in cases:
        outcome = outcomes[case.case_id]
        if outcome is None:
            failed_cases = failed_cases + 1
            case_result = BatchEvalResult(
                case_id=case.case_id,
                status="failed",
                score=None,
            )
            case_results.append(case_result)
        else:
            scored_cases = scored_cases + 1
            result = evaluation(case, outcome)
            case_result = BatchEvalResult(
                case_id=case.case_id,
                status="scored",
                score=result,
            )
            case_results.append(case_result)
            if result.passed == True:
                passed_cases = passed_cases + 1
    pass_rate = passed_cases / total_cases if total_cases != 0 else None
    return BatchEvalReport(
        total_cases=total_cases,
        scored_cases=scored_cases,
        failed_cases=failed_cases,
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        case_results=case_results,
    )
