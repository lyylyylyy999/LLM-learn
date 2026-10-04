import json

import pytest

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.batch_evaluation import evaluate_batch
from exercises.task_008_llm_evaluation.llm_evaluation import (
    EvalCase,
    ExpectedContent,
    Message,
    evaluation,
)


def make_case(case_id: str, conversation: str = "公开合成对话") -> EvalCase:
    return EvalCase(
        case_id=case_id,
        conversation=[Message(role="user", content=conversation)],
        expected_summary=[
            ExpectedContent(name="目标事实", acceptable_phrases=["目标事实"])
        ],
        expected_key_points=[
            ExpectedContent(name="关键点", acceptable_phrases=["关键点"])
        ],
        expected_action_items=[],
    )


def make_result(
    summary: str = "目标事实", action_items: list[str] | None = None
) -> AnalysisResult:
    return AnalysisResult(
        summary=summary,
        key_points=["关键点"],
        action_items=[] if action_items is None else action_items,
    )


def test_mixed_batch_counts_failures_in_pass_rate_and_keeps_case_order() -> None:
    cases = [make_case("first"), make_case("second"), make_case("third")]
    passing = make_result()
    failing = make_result(summary="没有命中摘要概念")
    outcomes = {"third": None, "second": failing, "first": passing}

    report = evaluate_batch(cases, outcomes)

    assert (
        report.total_cases,
        report.scored_cases,
        report.failed_cases,
        report.passed_cases,
    ) == (3, 2, 1, 1)
    assert report.pass_rate == pytest.approx(1 / 3)
    assert [item.case_id for item in report.case_results] == [
        "first",
        "second",
        "third",
    ]
    assert [item.status for item in report.case_results] == [
        "scored",
        "scored",
        "failed",
    ]
    assert report.case_results[0].score == evaluation(cases[0], passing)
    assert report.case_results[1].score == evaluation(cases[1], failing)
    assert report.case_results[1].score is not None
    assert report.case_results[1].score.passed is False
    assert report.case_results[2].score is None


def test_all_failed_and_empty_batch_have_distinct_pass_rates() -> None:
    cases = [make_case("first"), make_case("second")]

    all_failed = evaluate_batch(cases, {"first": None, "second": None})
    empty = evaluate_batch([], {})

    assert (all_failed.total_cases, all_failed.scored_cases) == (2, 0)
    assert (all_failed.failed_cases, all_failed.passed_cases) == (2, 0)
    assert all_failed.pass_rate == 0.0
    assert [item.status for item in all_failed.case_results] == ["failed", "failed"]
    assert (empty.total_cases, empty.scored_cases, empty.failed_cases) == (0, 0, 0)
    assert empty.passed_cases == 0
    assert empty.case_results == []
    assert empty.pass_rate is None


def test_single_scored_case_reuses_no_action_items_rule() -> None:
    case = make_case("single")
    result = make_result(action_items=["凭空产生的行动项"])

    report = evaluate_batch([case], {case.case_id: result})

    assert (report.total_cases, report.scored_cases, report.failed_cases) == (
        1,
        1,
        0,
    )
    assert report.passed_cases == 0
    assert report.pass_rate == 0.0
    assert report.case_results[0].score == evaluation(case, result)
    assert report.case_results[0].score is not None
    assert report.case_results[0].score.no_action_items_correct is False


@pytest.mark.parametrize(
    ("case_ids", "outcome_ids"),
    [
        (["same", "same"], ["same"]),
        (["first", "second"], ["first"]),
        (["first"], ["first", "extra"]),
        (["first", "second"], ["first", "extra"]),
        ([], ["extra"]),
    ],
    ids=["duplicate", "missing", "extra", "swapped-id", "empty-with-extra"],
)
def test_inconsistent_case_ids_raise_safe_value_error(
    case_ids: list[str], outcome_ids: list[str]
) -> None:
    secret = "PRIVATE_CONVERSATION_MARKER_012"
    cases = [make_case(case_id, conversation=secret) for case_id in case_ids]
    outcomes = dict.fromkeys(outcome_ids, None)

    with pytest.raises(ValueError) as raised:
        evaluate_batch(cases, outcomes)

    assert secret not in str(raised.value)


def test_report_serializes_without_raw_inputs_and_does_not_mutate_them() -> None:
    conversation_secret = "PRIVATE_CONVERSATION_MARKER_012"
    model_secret = "PRIVATE_MODEL_OUTPUT_MARKER_012"
    case = make_case("safe-id", conversation=conversation_secret)
    result = make_result(summary=f"目标事实 {model_secret}")
    cases = [case]
    outcomes = {case.case_id: result}
    original_case = case.model_dump(mode="json")
    original_result = result.model_dump(mode="json")
    original_keys = list(outcomes)

    report = evaluate_batch(cases, outcomes)
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)

    assert report.case_results[0].score == evaluation(case, result)
    assert conversation_secret not in serialized
    assert model_secret not in serialized
    assert case.model_dump(mode="json") == original_case
    assert result.model_dump(mode="json") == original_result
    assert cases == [case]
    assert list(outcomes) == original_keys
    assert outcomes[case.case_id] is result
