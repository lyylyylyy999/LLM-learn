import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import Mock

import openai
import pytest
from pydantic import ValidationError

from exercises.task_007_structured_analysis.structured_analysis import (
    ANALYSIS_INSTRUCTIONS,
    AnalysisResult,
    AnalysisSettings,
    LLMError,
    StructuredOutputError,
    structured_analysis,
)

TEST_MODEL = "deepseek-flash"


@pytest.mark.parametrize(
    ("summary", "key_points", "action_items"),
    [
        ("1", ["1", "2", "3"], ["1", "2"]),
        ("123", ["1"], ["1", "2"]),
        ("123", ["1", "2", "3", "4", "5"], ["1", "2"]),
        ("123", ["1", "2"], []),
        ("123", ["1", "2", "3"], ["1", "2", "3", "4", "5"]),
    ],
)
def test_analysis_result(
    summary: str,
    key_points: list[str],
    action_items: list[str],
) -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": summary,
                "key_points": key_points,
                "action_items": action_items,
            }
        ),
        id="test_analysis_result",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    input_text = "123"
    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )
    clock = Mock(side_effect=[10.0, 12.5])
    result = structured_analysis(
        client=client,
        input=input_text,
        settings=settings,
        clock=clock,
    )
    assert result.analysis.summary == summary
    assert result.analysis.key_points == key_points
    assert result.analysis.action_items == action_items
    assert result.response_id == "test_analysis_result"
    assert result.model == TEST_MODEL
    assert result.input_tokens == 50
    assert result.output_tokens == 20
    assert result.total_tokens == 70
    assert result.elapsed_seconds == 2.5
    client.responses.create.assert_called_once_with(
        model=TEST_MODEL,
        instructions=ANALYSIS_INSTRUCTIONS,
        input=input_text,
        max_output_tokens=300,
        text={
            "format": {
                "type": "json_schema",
                "name": "analysis_result",
                "schema": AnalysisResult.model_json_schema(),
            }
        },
    )


@pytest.mark.parametrize(
    ("summary", "key_points", "action_items"),
    [
        ("   ", ["关键点"], []),
        ("正常摘要", ["   "], []),
        ("正常摘要", ["关键点"], ["   "]),
    ],
)
def test_analysis_result_rejects_blank_strings(
    summary: str,
    key_points: list[str],
    action_items: list[str],
) -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(
            summary=summary,
            key_points=key_points,
            action_items=action_items,
        )


def test_analysis_result_schema_contains_non_blank_string_constraints() -> None:
    schema = AnalysisResult.model_json_schema()

    summary_schema = schema["properties"]["summary"]
    key_point_schema = schema["properties"]["key_points"]["items"]
    action_item_schema = schema["properties"]["action_items"]["items"]

    assert summary_schema["minLength"] == 1
    assert summary_schema["pattern"] == r"\S"

    assert key_point_schema["minLength"] == 1
    assert key_point_schema["pattern"] == r"\S"

    assert action_item_schema["minLength"] == 1
    assert action_item_schema["pattern"] == r"\S"


@pytest.mark.parametrize(
    ("input_text", "exception", "match"),
    [
        ("  ", ValueError, "不能输入空字符串或纯空白"),
        ("\t", ValueError, "不能输入空字符串或纯空白"),
        ("", ValueError, "不能输入空字符串或纯空白"),
        ("\n", ValueError, "不能输入空字符串或纯空白"),
    ],
)
def test_empty_input(
    input_text: str,
    exception: type[Exception],
    match: str,
) -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": "123",
                "key_points": ["1", "2"],
                "action_items": ["1"],
            }
        ),
        id="test_analysis_result",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )
    clock = Mock(side_effect=[10.0, 12.5])
    with pytest.raises(exception, match=match):
        structured_analysis(
            client=client,
            input=input_text,
            settings=settings,
            clock=clock,
        )
    assert clock.call_count == 0
    client.responses.create.assert_not_called()


@pytest.mark.parametrize(
    ("status", "output_text"),
    [
        (
            "incomplete",
            "summary='123', key_points=['1', '2'], action_itmes=['1', '2', '3']",
        ),
        ("completed", ""),
        ("incomplete", "\t"),
        ("incomplete", " "),
    ],
)
def test_incomplete_status_ang_empty_output(
    status: str,
    output_text: str,
) -> None:
    fake_response = SimpleNamespace(
        status=status,
        output_text=output_text,
        id="test_incomplete_status_ang_empty_output",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    input_text = "123"
    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )
    clock = Mock(side_effect=[10.0, 12.5])
    with pytest.raises(
        LLMError,
        match=f"响应失败，响应 ID: test_incomplete_status_ang_empty_output,状态: {status}",
    ):
        structured_analysis(
            client=client,
            input=input_text,
            settings=settings,
            clock=clock,
        )


@pytest.mark.parametrize(
    ("output_json"),
    [
        ('{"key_points": ["1", "2", "3"], "action_items": ["1"]'),
        ({"key_points": ["1", "2", "3"], "action_items": ["1"]}),
        ({"summary": "123", "action_items": ["1"]}),
        ({"summary": "123", "key_points": ["1", "2", "3"]}),
        (
            {
                "test": "123",
                "summary": "123",
                "key_points": ["1", "2", "3"],
                "action_items": ["1"],
            }
        ),
        ({"summary": 123, "key_points": ["1", "2", "3"], "action_items": ["1"]}),
        ({"summary": "123", "key_points": "1", "action_items": ["1"]}),
        ({"summary": "123", "key_points": ["1", "2", "3"], "action_items": True}),
        ({"summary": "123", "key_points": [], "action_items": ["1"]}),
        (
            {
                "summary": "123",
                "key_points": ["1", "2", "3"],
                "action_items": ["1", "2", "3", "4", "5", "6"],
            }
        ),
        (
            {
                "summary": "123",
                "key_points": ["1", "2", "3", "4", "5", "6"],
                "action_items": ["1", "2", "3"],
            }
        ),
    ],
)
def test_exception_field(output_json: dict[str, str]) -> None:
    if isinstance(output_json, str):
        output_text = output_json
    else:
        output_text = json.dumps(output_json)
    fake_response = SimpleNamespace(
        status="completed",
        output_text=output_text,
        id="test_exception_field",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    input_text = "123"
    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )
    clock = Mock(side_effect=[10.0, 12.5])
    with pytest.raises(StructuredOutputError, match="大模型结构化输出失败") as exc_info:
        structured_analysis(
            client=client,
            input=input_text,
            settings=settings,
            clock=clock,
        )
    assert str(exc_info.value) == "大模型结构化输出失败"
    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_sdk_error_propagates_unchanged() -> None:
    client = Mock()
    sdk_error = RuntimeError("sdk request failed")

    client.responses.create.side_effect = sdk_error

    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )
    clock = Mock(return_value=10.0)

    with pytest.raises(RuntimeError) as exc_info:
        structured_analysis(
            client=client,
            input="测试对话",
            settings=settings,
            clock=clock,
        )

    assert exc_info.value is sdk_error


def test_success_log_contains_metadata_without_sensitive_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_input = "SENSITIVE_CONVERSATION_MARKER"
    sensitive_output = "SENSITIVE_MODEL_OUTPUT_MARKER"

    fake_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": "正常摘要",
                "key_points": ["关键点"],
                "action_items": [],
            }
        ),
        id="resp_123",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )

    client = Mock()
    client.responses.create.return_value = fake_response

    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    clock = Mock(side_effect=[10.0, 12.5])

    with caplog.at_level(logging.INFO):
        structured_analysis(
            client=client,
            input=sensitive_input,
            settings=settings,
            clock=clock,
        )

    assert "LLM structured analysis succeeded" in caplog.text
    assert f"model={TEST_MODEL}" in caplog.text
    assert "response_id=resp_123" in caplog.text
    assert "input_tokens=50" in caplog.text
    assert "output_tokens=20" in caplog.text
    assert "total_tokens=70" in caplog.text
    assert "elapsed_seconds=2.500000" in caplog.text
    assert "validation_success=True" in caplog.text

    assert sensitive_input not in caplog.text
    assert sensitive_output not in caplog.text


def test_non_completed_response_logs_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_response = SimpleNamespace(
        status="incompletee",
        output_text=None,
        id="resp_incompletee",
        model=TEST_MODEL,
        usage=None,
    )

    client = Mock()
    client.responses.create.return_value = fake_response

    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    clock = Mock(side_effect=[10.0, 12.0])

    with caplog.at_level(logging.ERROR), pytest.raises(LLMError):
        structured_analysis(
            client=client,
            input="SENSITIVE_INPUT",
            settings=settings,
            clock=clock,
        )

    assert "LLM structured analysis failed" in caplog.text
    assert "status=incompletee" in caplog.text
    assert "response_id=resp_incompletee" in caplog.text

    assert "SENSITIVE_INPUT" not in caplog.text


def test_structured_output_failure_log_does_not_leak_sensitive_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_input = "SENSITIVE_INPUT_MARKER"
    sensitive_output = "SENSITIVE_MODEL_OUTPUT_MARKER"

    fake_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": "正常摘要",
                # 故意违反 list[str]，并把敏感标记放在失败值中
                "key_points": sensitive_output,
                "action_items": [],
            }
        ),
        id="resp_invalid",
        model=TEST_MODEL,
        usage=None,
    )

    client = Mock()
    client.responses.create.return_value = fake_response

    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    clock = Mock(side_effect=[10.0, 12.0])

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(StructuredOutputError) as exc_info,
    ):
        structured_analysis(
            client=client,
            input=sensitive_input,
            settings=settings,
            clock=clock,
        )

    assert isinstance(exc_info.value.__cause__, ValidationError)

    assert "LLM structured analysis failed" in caplog.text
    assert "resp_invalid" in caplog.text
    assert TEST_MODEL in caplog.text

    assert sensitive_input not in caplog.text
    assert sensitive_output not in caplog.text


def test_structured_analysis_returns_none_tokens_when_usage_missing() -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": "讨论了过拟合。",
                "key_points": ["过拟合会降低泛化能力。"],
                "action_items": [],
            }
        ),
        id="resp_no_usage",
        model=TEST_MODEL,
        usage=None,
    )

    client = Mock()
    client.responses.create.return_value = fake_response

    settings = AnalysisSettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    clock = Mock(side_effect=[10.0, 12.5])

    result = structured_analysis(
        client=client,
        input="讨论过拟合。",
        settings=settings,
        clock=clock,
    )

    assert result.analysis.summary == "讨论了过拟合。"
    assert result.analysis.key_points == ["过拟合会降低泛化能力。"]
    assert result.analysis.action_items == []

    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None

    assert result.response_id == "resp_no_usage"
    assert result.model == TEST_MODEL
    assert result.elapsed_seconds == 2.5


@pytest.mark.integration
def test_real_deepseek_structured_analysis_smoke() -> None:
    run_smoke = os.getenv("RUN_DEEPSEEK_SMOKE")

    if run_smoke != "1":
        pytest.skip("真实 DeepSeek 结构化输出冒烟测试未显式开启")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL")

    if not api_key or not api_key.strip():
        pytest.fail("RUN_DEEPSEEK_SMOKE=1，但未提供 DEEPSEEK_API_KEY")

    if not model or not model.strip():
        pytest.fail("RUN_DEEPSEEK_SMOKE=1，但未提供 DEEPSEEK_MODEL")

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    settings = AnalysisSettings(
        model=model,
        max_output_tokens=2000,
    )

    result = structured_analysis(
        client=client,
        input=(
            "学生：我理解过拟合就是模型在训练集上表现很好，"
            "但是在新的数据上表现比较差。\n"
            "老师：对。模型可能不仅学习了有效规律，"
            "还学习了训练数据中的噪声和偶然特征。\n"
            "学生：那我下一步准备训练一个基线模型，"
            "记录训练集和验证集的 loss，"
            "然后比较 L2 正则化和 early stopping 的效果。\n"
            "老师：可以，重点观察验证误差什么时候开始上升。"
        ),
        settings=settings,
    )

    print("\n--- DeepSeek structured analysis smoke test result ---")
    print(f"model: {result.model}")
    print(f"response_id: {result.response_id}")
    print(f"input_tokens: {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"total_tokens: {result.total_tokens}")
    print(f"elapsed_seconds: {result.elapsed_seconds:.6f}")
    print(f"summary_length: {len(result.analysis.summary)}")
    print(f"key_points_count: {len(result.analysis.key_points)}")
    print(f"action_items_count: {len(result.analysis.action_items)}")

    assert isinstance(result.analysis, AnalysisResult)

    assert result.analysis.summary.strip()
    assert 1 <= len(result.analysis.key_points) <= 5
    assert len(result.analysis.action_items) <= 5

    assert all(point.strip() for point in result.analysis.key_points)
    assert all(item.strip() for item in result.analysis.action_items)

    assert result.response_id
    assert result.model
    assert result.elapsed_seconds >= 0

    if result.input_tokens is not None:
        assert result.input_tokens > 0

    if result.output_tokens is not None:
        assert result.output_tokens > 0

    if result.total_tokens is not None:
        assert result.total_tokens > 0
