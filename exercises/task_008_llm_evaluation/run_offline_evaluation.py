import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from exercises.task_007_structured_analysis.structured_analysis import AnalysisResult
from exercises.task_008_llm_evaluation.batch_evaluation import (
    BatchEvalReport,
    evaluate_batch,
)
from exercises.task_008_llm_evaluation.llm_evaluation import verify_evaluation_set


class OutcomMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    result: AnalysisResult | None


def run_offline_evaluation(
    case_path: Path | str,
    outcome_path: Path | str,
    report_path: Path | str,
    *,
    scorer_version: str,
) -> "BatchEvalReport":
    outcome_map: dict[str, AnalysisResult | None] = {}
    seen_outcome_ids: set[str] = set()
    case_path = Path(case_path)
    cases_sha256 = hashlib.sha256(case_path.read_bytes()).hexdigest()
    outcome_path = Path(outcome_path)
    outcomes_sha256 = hashlib.sha256(outcome_path.read_bytes()).hexdigest()
    report_path = Path(report_path)
    cases = verify_evaluation_set(case_path)
    with open(outcome_path, "r", encoding="UTF-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line.strip() == "":
                continue
            try:
                outcome = OutcomMessage.model_validate(line)
            except ValueError:
                raise ValueError(f"第{line_number}行数据校验失败") from None
            if outcome.case_id in seen_outcome_ids:
                raise ValueError("outcomes 存在重复 ID")
            seen_outcome_ids.add(outcome.case_id)
            outcome_map[outcome.case_id] = outcome.result
    batch_report = evaluate_batch(cases, outcome_map)
    payload = {
        "schema_version": 1,
        "scorer_version": scorer_version,
        "cases_sha256": cases_sha256,
        "outcomes_sha256": outcomes_sha256,
        "report": batch_report.model_dump(),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )
    with report_path.open("x", encoding="utf-8") as f:
        f.write(serialized)
    return batch_report
