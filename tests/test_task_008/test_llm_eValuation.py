import json
import traceback
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.llm_evaluation import (
    EvalCase,
    EvaluationDataError,
    ExpectedContent,
    Message,
    count_matched_concepts,
    evaluation,
    verify_evaluation_set,
)

# ============================================================
# Test helpers
# ============================================================


def valid_case() -> dict[str, Any]:
    """返回一个合法的 JSONL case 原始字典。"""
    return {
        "case_id": "case-001",
        "conversation": [
            {
                "role": "user",
                "content": "hello",
            }
        ],
        "expected_summary": [
            {
                "name": "summary",
                "acceptable_phrases": ["hello"],
            }
        ],
        "expected_key_points": [],
        "expected_action_items": [],
    }


def expected(name: str, *phrases: str) -> ExpectedContent:
    """快速创建一个期望概念。"""
    return ExpectedContent(
        name=name,
        acceptable_phrases=list(phrases),
    )


def make_case(
    *,
    summary: list[ExpectedContent] | None = None,
    key_points: list[ExpectedContent] | None = None,
    action_items: list[ExpectedContent] | None = None,
) -> EvalCase:
    """
    创建评分测试使用的 EvalCase。

    None 表示使用默认概念；
    [] 表示该类别没有任何期望概念。
    """
    return EvalCase(
        case_id="case-001",
        conversation=[
            Message(
                role="user",
                content="test",
            )
        ],
        expected_summary=(
            [expected("summary", "summary phrase")] if summary is None else summary
        ),
        expected_key_points=(
            [expected("key point", "key phrase")] if key_points is None else key_points
        ),
        expected_action_items=(
            [expected("action", "action phrase")]
            if action_items is None
            else action_items
        ),
    )


def write_jsonl(
    path: Path,
    *records: dict[str, Any],
) -> None:
    text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)

    path.write_text(
        text + "\n",
        encoding="utf-8",
    )


# ============================================================
# verify_evaluation_set
# ============================================================


def test_load_jsonl() -> None:
    cases = verify_evaluation_set(Path("evals/task_008/cases.jsonl"))

    assert len(cases) == 3
    assert cases[0].case_id == "case_001_knowledge_only"
    assert cases[1].case_id == "case_002_single_action"
    assert cases[2].case_id == "case_003_multiple_facts_actions"


def test_skip_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"

    case1 = valid_case()
    case2 = {
        **valid_case(),
        "case_id": "case-002",
    }

    path.write_text(
        "\n" + json.dumps(case1) + "\n\n" + json.dumps(case2) + "\n",
        encoding="utf-8",
    )

    cases = verify_evaluation_set(path)

    assert len(cases) == 2
    assert cases[0].case_id == "case-001"
    assert cases[1].case_id == "case-002"


def test_invalid_json_raises_evaluation_data_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    path.write_text(
        '{"case_id": "case-001"\n',
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationDataError,
        match="第1行存在不合法 JSON",
    ) as exc_info:
        verify_evaluation_set(path)

    # 保证对外抛出的确实是专门的评测数据异常
    assert type(exc_info.value) is EvaluationDataError


@pytest.mark.parametrize(
    "missing_field",
    [
        "case_id",
        "conversation",
        "expected_summary",
        "expected_key_points",
        "expected_action_items",
    ],
)
def test_missing_field_is_rejected(
    tmp_path: Path,
    missing_field: str,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case.pop(missing_field)

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


def test_top_level_extra_field_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["unexpected"] = "value"

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


def test_message_extra_field_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["conversation"][0]["unexpected"] = "value"

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


def test_expected_content_extra_field_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["expected_summary"][0]["unexpected"] = "value"

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


@pytest.mark.parametrize(
    "case_id",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_blank_case_id_is_rejected(
    tmp_path: Path,
    case_id: str,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["case_id"] = case_id

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_blank_message_content_is_rejected(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["conversation"][0]["content"] = content

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


@pytest.mark.parametrize(
    "phrase",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_blank_acceptable_phrase_is_rejected(
    tmp_path: Path,
    phrase: str,
) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["expected_summary"][0]["acceptable_phrases"] = [phrase]

    write_jsonl(path, case)

    with pytest.raises(
        EvaluationDataError,
        match="第1行数据校验失败",
    ):
        verify_evaluation_set(path)


def test_duplicate_case_id_and_error_does_not_expose_conversation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    first = valid_case()
    second = valid_case()

    sensitive_content = "SECRET-CONVERSATION-CONTENT-THIS-MUST-NOT-APPEAR-IN-ERROR"

    second["conversation"][0]["content"] = sensitive_content

    write_jsonl(
        path,
        first,
        second,
    )

    with pytest.raises(EvaluationDataError) as exc_info:
        verify_evaluation_set(path)

    message = str(exc_info.value)

    assert "第2行" in message
    assert "case_id 存在重复" in message

    # 敏感内容确实存在于触发失败的第二条记录中，
    # 但异常消息不能泄露它。
    assert sensitive_content not in message


def test_missing_file_remains_file_not_found_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "does-not-exist.jsonl"

    with pytest.raises(FileNotFoundError):
        verify_evaluation_set(path)


# ============================================================
# count_matched_concepts
# ============================================================


def test_any_acceptable_phrase_can_match_concept() -> None:
    concepts = [
        expected(
            "retry",
            "retry mechanism",
            "automatic retry",
            "retry on failure",
        )
    ]

    output = "The system should use an automatic retry when the request fails."

    assert count_matched_concepts(output, concepts) == 1


def test_same_concept_is_counted_once_when_two_phrases_match() -> None:
    concepts = [
        expected(
            "retry",
            "retry mechanism",
            "automatic retry",
        )
    ]

    output = "The system uses a retry mechanism and also supports automatic retry."

    # 两个 phrase 同时出现，
    # 但计分单位是 concept，因此只能算 1 次。
    assert count_matched_concepts(output, concepts) == 1


@pytest.mark.parametrize(
    ("output", "phrase"),
    [
        ("HELLO WORLD", "hello world"),
        ("hello\tworld", "hello world"),
        ("hello\nworld", "hello world"),
        ("hello    world", "hello world"),
        ("  HeLLo \t\n   WoRLD  ", "hello world"),
    ],
)
def test_matching_normalizes_case_and_whitespace(
    output: str,
    phrase: str,
) -> None:
    concepts = [
        expected(
            "greeting",
            phrase,
        )
    ]

    assert count_matched_concepts(output, concepts) == 1


def test_matching_merged_list_text() -> None:
    concepts = [
        expected(
            "retry",
            "automatic retry",
        )
    ]

    output = [
        "automatic",
        "retry",
    ]

    # 如果 list[str] 按要求先合并，
    # "automatic" + "retry" 应形成 "automatic retry"。
    assert count_matched_concepts(output, concepts) == 1


# ============================================================
# evaluation - field isolation
# ============================================================


def test_summary_phrase_does_not_match_other_sections() -> None:
    case = EvalCase(
        case_id="case-001",
        conversation=[
            Message(
                role="user",
                content="test",
            )
        ],
        expected_summary=[
            expected(
                "summary",
                "summary phrase",
            )
        ],
        expected_key_points=[
            expected(
                "key",
                "key point phrase",
            )
        ],
        expected_action_items=[
            expected(
                "action",
                "action item phrase",
            )
        ],
    )

    result = AnalysisResult(
        summary=("summary phrase key point phrase action item phrase"),
        key_points=[
            "没有匹配内容",
        ],
        action_items=[
            "没有匹配内容",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 1
    assert eval_result.key_points_match_count == 0
    assert eval_result.action_items_match_count == 0


# ============================================================
# evaluation - coverage
# ============================================================


def make_full_eval_case() -> EvalCase:
    return EvalCase(
        case_id="case-full",
        conversation=[
            Message(
                role="user",
                content="test",
            )
        ],
        expected_summary=[
            expected("summary-1", "alpha"),
            expected("summary-2", "beta"),
        ],
        expected_key_points=[
            expected("key-1", "gamma"),
            expected("key-2", "delta"),
        ],
        expected_action_items=[
            expected("action-1", "epsilon"),
            expected("action-2", "zeta"),
        ],
    )


def test_evaluation_all_matched() -> None:
    case = make_full_eval_case()

    result = AnalysisResult(
        summary="alpha and beta",
        key_points=[
            "gamma",
            "delta",
        ],
        action_items=[
            "epsilon",
            "zeta",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 2
    assert eval_result.key_points_match_count == 2
    assert eval_result.action_items_match_count == 2

    assert eval_result.summary_coverage == 1.0
    assert eval_result.key_points_coverage == 1.0
    assert eval_result.action_items_coverage == 1.0

    assert eval_result.passed is True


def test_evaluation_partially_matched() -> None:
    case = make_full_eval_case()

    result = AnalysisResult(
        summary="alpha",
        key_points=[
            "gamma",
        ],
        action_items=[
            "epsilon",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 1
    assert eval_result.key_points_match_count == 1
    assert eval_result.action_items_match_count == 1

    assert eval_result.summary_coverage == 0.5
    assert eval_result.key_points_coverage == 0.5
    assert eval_result.action_items_coverage == 0.5

    assert eval_result.passed is False


def test_evaluation_nothing_matched() -> None:
    case = make_full_eval_case()

    result = AnalysisResult(
        summary="unrelated summary",
        key_points=[
            "unrelated key point",
        ],
        action_items=[
            "unrelated action",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 0
    assert eval_result.key_points_match_count == 0
    assert eval_result.action_items_match_count == 0

    assert eval_result.summary_coverage == 0.0
    assert eval_result.key_points_coverage == 0.0
    assert eval_result.action_items_coverage == 0.0

    assert eval_result.passed is False


# ============================================================
# evaluation - action items
# ============================================================


def test_case_with_expected_action_items() -> None:
    case = make_case()

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "key phrase",
        ],
        action_items=[
            "action phrase",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_match_count == 1
    assert eval_result.action_items_coverage == 1.0

    # 有预期 action item 时，
    # no_action_items_correct 不适用。
    assert eval_result.no_action_items_correct is None
    assert eval_result.passed is True


def test_case_without_expected_action_items() -> None:
    case = make_case(
        action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "key phrase",
        ],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_match_count == 0
    assert eval_result.action_items_coverage is None
    assert eval_result.no_action_items_correct is True
    assert eval_result.passed is True


def test_unexpected_action_item_causes_failure() -> None:
    case = make_case(
        action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "key phrase",
        ],
        action_items=[
            "模型凭空生成的行动项",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_coverage is None
    assert eval_result.no_action_items_correct is False

    # 即使 summary/key points 全部正确，
    # 凭空生成行动项仍必须导致整体失败。
    assert eval_result.summary_coverage == 1.0
    assert eval_result.key_points_coverage == 1.0
    assert eval_result.passed is False


# ============================================================
# evaluation - empty expected concepts
# ============================================================


def test_empty_expected_action_items_has_none_coverage() -> None:
    case = make_case(
        action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "key phrase",
        ],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_match_count == 0
    assert eval_result.action_items_coverage is None
    assert eval_result.no_action_items_correct is True


def test_empty_expected_summary_has_none_coverage() -> None:
    case = make_case(
        summary=[],
        action_items=[],
    )

    result = AnalysisResult(
        summary="任何内容",
        key_points=[
            "key phrase",
        ],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 0
    assert eval_result.summary_coverage is None


def test_empty_expected_key_points_has_none_coverage() -> None:
    case = make_case(
        key_points=[],
        action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "任何内容",
        ],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.key_points_match_count == 0
    assert eval_result.key_points_coverage is None


def test_all_expected_concepts_empty_do_not_divide_by_zero() -> None:
    case = make_case(
        summary=[],
        key_points=[],
        action_items=[],
    )

    result = AnalysisResult(
        summary="anything",
        key_points=["anything"],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_coverage is None
    assert eval_result.key_points_coverage is None
    assert eval_result.action_items_coverage is None
    assert eval_result.no_action_items_correct is True


# ============================================================
# immutability / side effects
# ============================================================


def test_evaluation_does_not_modify_inputs() -> None:
    case = EvalCase(
        case_id="case-001",
        conversation=[
            Message(
                role="user",
                content="Original Conversation",
            )
        ],
        expected_summary=[
            expected(
                "summary",
                "Summary Phrase",
            )
        ],
        expected_key_points=[
            expected(
                "key",
                "Key Phrase",
            )
        ],
        expected_action_items=[
            expected(
                "action",
                "Action Phrase",
            )
        ],
    )

    result = AnalysisResult(
        summary="SUMMARY PHRASE",
        key_points=[
            "KEY PHRASE",
        ],
        action_items=[
            "ACTION PHRASE",
        ],
    )

    original_case = case.model_copy(deep=True)
    original_result = result.model_copy(deep=True)

    evaluation(case, result)

    assert case == original_case
    assert result == original_result


def test_eval_result_is_immutable() -> None:
    case = make_case()

    result = AnalysisResult(
        summary="summary phrase",
        key_points=[
            "key phrase",
        ],
        action_items=[
            "action phrase",
        ],
    )

    eval_result = evaluation(case, result)

    assert eval_result.passed is True

    with pytest.raises(ValidationError):
        eval_result.passed = False

    # 修改失败后原值仍然存在。
    assert eval_result.passed is True


def test_validation_traceback_does_not_expose_sensitive_conversation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.jsonl"

    sensitive = "SECRET-FULL-CONVERSATION-MARKER"

    case = valid_case()

    # conversation 应为 list[Message]，故意传入敏感字符串，
    # 确保进入 Pydantic ValidationError 路径。
    case["conversation"] = sensitive

    path.write_text(
        json.dumps(case, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationDataError) as exc_info:
        verify_evaluation_set(path)

    full_traceback = "".join(traceback.format_exception(exc_info.value))

    assert "第1行数据校验失败" in full_traceback
    assert sensitive not in full_traceback
