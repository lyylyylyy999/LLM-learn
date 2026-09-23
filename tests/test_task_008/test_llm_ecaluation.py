import json
from pathlib import Path

import pytest

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.llm_evaluation import EvalCase, ExceptedContent, Message, count_matched_concepts, evaluation, verify_evaluation_set


def valid_case() -> dict:
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


def test_load_jsonl() -> None:
    cases = verify_evaluation_set("evals/task_008/cases.jsonl")
    assert len(cases) == 3
    assert cases[0].case_id == "case_001_knowledge_only"
    assert cases[1].case_id == "case_002_single_action"
    assert cases[2].case_id == "case_003_multiple_facts_actions"


def test_skip_blank(tmp_path: Path) -> None:
    path = tmp_path / "test.jsonl"
    case = valid_case()
    path.write_text(
        "\n"
        + json.dumps(case)
        + "\n\n"
        + json.dumps({**case, "case_id": "case-002"})
        + "\n",
        encoding="utf-8",
    )
    cases = verify_evaluation_set(path)
    assert len(cases) == 2
    assert cases[0].case_id == "case-001"
    assert cases[1].case_id == "case-002"


def test_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "test.jsonl"
    path.write_text(
        '{"case_id": "case-001"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="第1行存在不合法 JSON"):
        verify_evaluation_set(path)


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
def test_missing_field(tmp_path, missing_field: str) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case.pop(missing_field)

    path.write_text(
        json.dumps(case),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="第1行数据校验失败"):
        verify_evaluation_set(path)


def test_extra_field(tmp_path) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case["unexpected"] = "value"

    path.write_text(
        json.dumps(case),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="第1行数据校验失败"):
        verify_evaluation_set(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", ""),
        ("case_id", "   "),
    ],
)
def test_blank_case_id(tmp_path, field: str, value: str) -> None:
    path = tmp_path / "cases.jsonl"

    case = valid_case()
    case[field] = value

    path.write_text(
        json.dumps(case),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="第1行数据校验失败"):
        verify_evaluation_set(path)


def test_same_case_id(tmp_path: Path) -> None:
    path = tmp_path / "test.jsonl"
    case = valid_case()
    path.write_text(
        "\n"
        + json.dumps(case)
        + "\n\n"
        + json.dumps(case)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="在第4行 case_id 存在重复"):
        verify_evaluation_set(path)


def test_same_concept_with_multiple_acceptable_phrases() -> None:
    concepts = [
        ExceptedContent(
            name="重试机制",
            acceptable_phrases=[
                "retry mechanism",
                "automatic retry",
                "retry on failure",
            ],
        )
    ]

    output = "The system should use an automatic retry when the request fails."

    result = count_matched_concepts(output, concepts)

    assert result == 1


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
def test_text_normalization_matching(output: str, phrase: str) -> None:
    concepts = [
        ExceptedContent(
            name="greeting",
            acceptable_phrases=[phrase],
        )
    ]

    result = count_matched_concepts(output, concepts)

    assert result == 1


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
            ExceptedContent(
                name="summary concept",
                acceptable_phrases=["summary phrase"],
            )
        ],
        expected_key_points=[
            ExceptedContent(
                name="key point concept",
                acceptable_phrases=["key point phrase"],
            )
        ],
        expected_action_items=[
            ExceptedContent(
                name="action item concept",
                acceptable_phrases=["action item phrase"],
            )
        ],
    )

    result = AnalysisResult(
        summary=(
            "summary phrase "
            "key point phrase "
            "action item phrase"
        ),
        key_points=["没有匹配内容"],
        action_items=["没有匹配内容"],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 1
    assert eval_result.key_points_match_count == 0
    assert eval_result.action_items_match_count == 0


def make_eval_case() -> EvalCase:
    return EvalCase(
        case_id="case-001",
        conversation=[
            Message(role="user", content="test")
        ],
        expected_summary=[
            ExceptedContent(
                name="summary-1",
                acceptable_phrases=["alpha"],
            ),
            ExceptedContent(
                name="summary-2",
                acceptable_phrases=["beta"],
            ),
        ],
        expected_key_points=[
            ExceptedContent(
                name="key-1",
                acceptable_phrases=["gamma"],
            ),
            ExceptedContent(
                name="key-2",
                acceptable_phrases=["delta"],
            ),
        ],
        expected_action_items=[
            ExceptedContent(
                name="action-1",
                acceptable_phrases=["epsilon"],
            ),
            ExceptedContent(
                name="action-2",
                acceptable_phrases=["zeta"],
            ),
        ],
    )


def test_evaluation_all_matched() -> None:
    case = make_eval_case()
    result = AnalysisResult(
        summary="alpha and beta",
        key_points=["gamma", "delta"],
        action_items=["epsilon", "zeta"],
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
    case = make_eval_case()
    result = AnalysisResult(
        summary="alpha",
        key_points=["gamma"],
        action_items=["epsilon"],
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
    case = make_eval_case()
    result = AnalysisResult(
        summary="unrelated summary",
        key_points=["unrelated key point"],
        action_items=["unrelated action"],
    )

    eval_result = evaluation(case, result)

    assert eval_result.summary_match_count == 0
    assert eval_result.key_points_match_count == 0
    assert eval_result.action_items_match_count == 0

    assert eval_result.summary_coverage == 0.0
    assert eval_result.key_points_coverage == 0.0
    assert eval_result.action_items_coverage == 0.0

    assert eval_result.passed is False


def test_case_with_action_items() -> None:
    case = EvalCase(
        case_id="case-with-actions",
        conversation=[
            Message(role="user", content="test")
        ],
        expected_summary=[
            ExceptedContent(
                name="summary",
                acceptable_phrases=["summary phrase"],
            )
        ],
        expected_key_points=[
            ExceptedContent(
                name="key point",
                acceptable_phrases=["key phrase"],
            )
        ],
        expected_action_items=[
            ExceptedContent(
                name="action",
                acceptable_phrases=["submit report"],
            )
        ],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=["key phrase"],
        action_items=["Please submit report tomorrow."],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_excepted_count == 1
    assert eval_result.action_items_match_count == 1
    assert eval_result.action_items_coverage == 1.0

    # 有预期行动项时，“无行动项检查”不适用
    assert eval_result.no_action_items_correct is None

    assert eval_result.passed is True


def test_case_without_action_items() -> None:
    case = EvalCase(
        case_id="case-without-actions",
        conversation=[
            Message(role="user", content="test")
        ],
        expected_summary=[
            ExceptedContent(
                name="summary",
                acceptable_phrases=["summary phrase"],
            )
        ],
        expected_key_points=[
            ExceptedContent(
                name="key point",
                acceptable_phrases=["key phrase"],
            )
        ],
        expected_action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=["key phrase"],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_excepted_count == 0
    assert eval_result.action_items_match_count == 0
    assert eval_result.action_items_coverage is None
    assert eval_result.no_action_items_correct is True
    assert eval_result.passed is True


def test_empty_expected_action_items_has_none_coverage() -> None:
    case = EvalCase(
        case_id="case-no-actions",
        conversation=[
            Message(role="user", content="test"),
        ],
        expected_summary=[
            ExceptedContent(
                name="summary",
                acceptable_phrases=["summary phrase"],
            )
        ],
        expected_key_points=[
            ExceptedContent(
                name="key point",
                acceptable_phrases=["key phrase"],
            )
        ],
        expected_action_items=[],
    )

    result = AnalysisResult(
        summary="summary phrase",
        key_points=["key phrase"],
        action_items=[],
    )

    eval_result = evaluation(case, result)

    assert eval_result.action_items_excepted_count == 0
    assert eval_result.action_items_match_count == 0
    assert eval_result.action_items_coverage is None


from copy import deepcopy


def test_evaluation_does_not_modify_inputs() -> None:
    case = EvalCase(
        case_id="case-001",
        conversation=[
            Message(role="user", content="test"),
        ],
        expected_summary=[
            ExceptedContent(
                name="summary",
                acceptable_phrases=["Summary Phrase"],
            )
        ],
        expected_key_points=[
            ExceptedContent(
                name="key point",
                acceptable_phrases=["Key Phrase"],
            )
        ],
        expected_action_items=[
            ExceptedContent(
                name="action",
                acceptable_phrases=["Action Phrase"],
            )
        ],
    )

    result = AnalysisResult(
        summary="SUMMARY PHRASE",
        key_points=["KEY PHRASE"],
        action_items=["ACTION PHRASE"],
    )

    original_case = deepcopy(case)
    original_result = deepcopy(result)

    evaluation(case, result)

    assert case == original_case
    assert result == original_result