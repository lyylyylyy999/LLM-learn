import hashlib
import json
import traceback
from pathlib import Path

import pytest

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.batch_evaluation import evaluate_batch
from exercises.task_008_llm_evaluation.llm_evaluation import (
    EvalCase,
    EvaluationDataError,
    ExpectedContent,
    Message,
)
from exercises.task_008_llm_evaluation.run_offline_evaluation import (
    run_offline_evaluation,
)


def make_case(case_id: str, conversation: str = "公开合成对话") -> EvalCase:
    return EvalCase(
        case_id=case_id,
        conversation=[Message(role="user", content=conversation)],
        expected_summary=[
            ExpectedContent(name="摘要事实", acceptable_phrases=["摘要事实"])
        ],
        expected_key_points=[
            ExpectedContent(name="关键事实", acceptable_phrases=["关键事实"])
        ],
        expected_action_items=[],
    )


def make_result(summary: str = "摘要事实") -> AnalysisResult:
    return AnalysisResult(summary=summary, key_points=["关键事实"], action_items=[])


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def outcome_row(case_id: str, result: AnalysisResult | None) -> dict[str, object]:
    return {
        "case_id": case_id,
        "result": None if result is None else result.model_dump(mode="json"),
    }


def test_run_scores_in_case_order_and_saves_reproducible_report(tmp_path: Path) -> None:
    first = make_case("first")
    second = make_case("second")
    passing = make_result()
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    write_jsonl(
        case_path, [first.model_dump(mode="json"), second.model_dump(mode="json")]
    )
    write_jsonl(
        outcome_path, [outcome_row("second", None), outcome_row("first", passing)]
    )

    report_path = tmp_path / "report.json"
    other_path = tmp_path / "same-report.json"
    report = run_offline_evaluation(
        case_path, outcome_path, report_path, scorer_version="rules-v1"
    )
    run_offline_evaluation(
        str(case_path), str(outcome_path), str(other_path), scorer_version="rules-v1"
    )

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert report == evaluate_batch([first, second], {"first": passing, "second": None})
    assert saved["report"] == report.model_dump(mode="json")
    assert [row["case_id"] for row in saved["report"]["case_results"]] == [
        "first",
        "second",
    ]
    assert (report.total_cases, report.scored_cases, report.failed_cases) == (2, 1, 1)
    assert saved["schema_version"] == 1
    assert saved["scorer_version"] == "rules-v1"
    assert saved["cases_sha256"] == hashlib.sha256(case_path.read_bytes()).hexdigest()
    assert (
        saved["outcomes_sha256"]
        == hashlib.sha256(outcome_path.read_bytes()).hexdigest()
    )
    assert report_path.read_bytes() == other_path.read_bytes()


def test_empty_files_produce_empty_report(tmp_path: Path) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    case_path.write_text("\n", encoding="utf-8")
    outcome_path.write_text("\n", encoding="utf-8")
    report_path = tmp_path / "report.json"

    report = run_offline_evaluation(
        case_path, outcome_path, report_path, scorer_version="rules-v1"
    )

    assert report.total_cases == 0
    assert report.case_results == []
    assert report.pass_rate is None
    assert json.loads(report_path.read_text(encoding="utf-8"))["report"] == (
        report.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    ("rows", "error_kind"),
    [
        ([outcome_row("first", None), outcome_row("first", None)], "duplicate"),
        ([outcome_row("extra", None)], "id-mismatch"),
        ([], "id-mismatch"),
        ([{"case_id": "first", "result": {"summary": "invalid"}}], "line"),
        ([{"case_id": "first"}], "line"),
        ([{"case_id": "first", "result": None, "unexpected": True}], "line"),
        ([{"case_id": " ", "result": None}], "line"),
    ],
    ids=[
        "duplicate-id",
        "missing-and-extra-id",
        "missing-id",
        "invalid-result",
        "missing-result",
        "extra-field",
        "blank-id",
    ],
)
def test_invalid_outcomes_fail_without_creating_report(
    tmp_path: Path, rows: list[object], error_kind: str
) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    write_jsonl(case_path, [make_case("first").model_dump(mode="json")])
    write_jsonl(outcome_path, rows)

    with pytest.raises(Exception) as raised:
        run_offline_evaluation(
            case_path, outcome_path, report_path, scorer_version="rules-v1"
        )

    assert str(raised.value)
    if error_kind == "duplicate":
        assert (
            "2" in str(raised.value)
            or "重复" in str(raised.value)
            or "duplicate" in str(raised.value).lower()
        )
    elif error_kind == "id-mismatch":
        assert "id" in str(raised.value).lower()
    else:
        assert "1" in str(raised.value)
    assert not report_path.exists()


def test_invalid_case_input_does_not_create_report(tmp_path: Path) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    case_path.write_text("{invalid json}\n", encoding="utf-8")
    outcome_path.write_text("", encoding="utf-8")

    with pytest.raises(EvaluationDataError):
        run_offline_evaluation(
            case_path, outcome_path, report_path, scorer_version="rules-v1"
        )

    assert not report_path.exists()


def test_invalid_outcome_json_does_not_create_report(tmp_path: Path) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    write_jsonl(case_path, [make_case("first").model_dump(mode="json")])
    outcome_path.write_text("{invalid json}\n", encoding="utf-8")

    with pytest.raises(Exception) as raised:
        run_offline_evaluation(
            case_path, outcome_path, report_path, scorer_version="rules-v1"
        )

    assert str(raised.value)
    assert not report_path.exists()


def test_report_and_validation_error_do_not_expose_raw_content(tmp_path: Path) -> None:
    conversation_secret = "PRIVATE_CONVERSATION_MARKER_013"
    result_secret = "PRIVATE_RESULT_MARKER_013"
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    case = make_case("safe-id", conversation=conversation_secret)
    result = make_result(summary=f"摘要事实 {result_secret}")
    write_jsonl(case_path, [case.model_dump(mode="json")])
    write_jsonl(outcome_path, [outcome_row("safe-id", result)])

    report = run_offline_evaluation(
        case_path, outcome_path, report_path, scorer_version="rules-v1"
    )

    saved = report_path.read_text(encoding="utf-8")
    assert (
        report.case_results[0].score
        == evaluate_batch([case], {"safe-id": result}).case_results[0].score
    )
    assert conversation_secret not in saved
    assert result_secret not in saved

    invalid_path = tmp_path / "invalid-outcomes.jsonl"
    write_jsonl(
        invalid_path,
        [
            {
                "case_id": "safe-id",
                "result": {
                    "summary": result_secret,
                    "key_points": [],
                    "action_items": [],
                },
            }
        ],
    )
    with pytest.raises(ValueError) as raised:
        run_offline_evaluation(
            case_path,
            invalid_path,
            tmp_path / "failed-report.json",
            scorer_version="rules-v1",
        )
    assert result_secret not in str(raised.value)
    assert result_secret not in "".join(traceback.format_exception(raised.value))
    assert not (tmp_path / "failed-report.json").exists()


def test_existing_report_is_not_overwritten(tmp_path: Path) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    case_path.write_text("", encoding="utf-8")
    outcome_path.write_text("", encoding="utf-8")
    report_path.write_text("existing report", encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_offline_evaluation(
            case_path, outcome_path, report_path, scorer_version="rules-v1"
        )

    assert report_path.read_text(encoding="utf-8") == "existing report"


@pytest.mark.parametrize("version", ["", " ", "\t\n"])
def test_blank_scorer_version_is_rejected_without_file(
    tmp_path: Path, version: str
) -> None:
    case_path = tmp_path / "cases.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    report_path = tmp_path / "report.json"
    case_path.write_text("", encoding="utf-8")
    outcome_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        run_offline_evaluation(
            case_path, outcome_path, report_path, scorer_version=version
        )

    assert not report_path.exists()
