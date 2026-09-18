import logging
import os
import pytest
import httpx2
import openai
from exercises.task_006_llm_summary.llm_summary import (
    llm_summary,
    SuccessResult,
    SummarySettings,
    LLMError,
)
from types import SimpleNamespace
from unittest.mock import Mock


TEST_MODEL = "deepseek-flash"


def test_normal_response() -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text="这是一段摘要",
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
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model=TEST_MODEL, max_output_tokens=16)
    result = llm_summary(
        client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
    )
    assert result == SuccessResult(
        summary_text="这是一段摘要",
        response_id="resp_123",
        response_model=TEST_MODEL,
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        elapsed_seconds=2.5,
    )
    client.responses.create.assert_called_once_with(
        model=TEST_MODEL,
        instructions=(
            "请将输入的对话总结为一段简洁、准确的摘要。"
            "重点保留核心讨论内容、关键结论和重要事实。"
            "不得添加原文中不存在的信息。"
            "只返回摘要正文，不要返回 JSON、字段描述或其他解释。"
        ),
        input="什么是过拟合?",
        max_output_tokens=16,
        store=False,
    )
    assert clock.call_count == 2


@pytest.mark.parametrize(
    ("model", "max_output_tokens", "exception", "match"),
    [
        ("", 300, ValueError, "model 不能是空字符串或者纯空白模型名"),
        ("  ", 300, ValueError, "model 不能是空字符串或者纯空白模型名"),
        ("\n", 300, ValueError, "model 不能是空字符串或者纯空白模型名"),
        ("test", 1, ValueError, "max_output_tokens 不能小于 16"),
        ("test", 15, ValueError, "max_output_tokens 不能小于 16"),
        ("test", 0, ValueError, "max_output_tokens 不能小于 16"),
        ("test", -300, ValueError, "max_output_tokens 不能小于 16"),
    ],
)
def test_exception_settings(
    model: str, max_output_tokens: int, exception: type[Exception], match: str
) -> None:
    with pytest.raises(exception, match=match):
        SummarySettings(
            model=model,
            max_output_tokens=max_output_tokens,
        )


@pytest.mark.parametrize("text", ["", "  ", "\n"])
def test_empty_text(text: str) -> None:
    client = Mock()
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    with pytest.raises(
        ValueError,
        match="拒绝空字符串或纯空白对话",
    ):
        llm_summary(
            client=client,
            text=text,
            summary_settings=settings,
            clock=clock,
        )

    assert clock.call_count == 0
    client.responses.create.assert_not_called()


@pytest.mark.parametrize(
    ("status", "exception", "id"),
    [
        ("failed", LLMError, "faild_id"),
        ("incomplete", LLMError, "incomplete_id"),
    ],
)
def test_exception_status(status: str, exception: type[Exception], id: str) -> None:
    fake_response = SimpleNamespace(
        status=status,
        output_text="这是一段摘要",
        id=id,
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model=TEST_MODEL, max_output_tokens=300)
    with pytest.raises(exception, match=f"发生异常，响应 ID: {id},状态: {status}"):
        llm_summary(
            client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
        )


@pytest.mark.parametrize(
    ("output_text", "exception"),
    [
        ("", LLMError),
        ("  ", LLMError),
        ("\n", LLMError),
    ],
)
def test_completed_but_output_text_is_empty(
    output_text: str, exception: type[Exception]
) -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text=output_text,
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
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model=TEST_MODEL, max_output_tokens=300)
    with pytest.raises(exception, match="发生异常，响应 ID: resp_123,状态: completed"):
        llm_summary(
            client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
        )


def test_usage_is_None() -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text="这是一段摘要",
        id="resp_123",
        model=TEST_MODEL,
        usage=None,
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model=TEST_MODEL, max_output_tokens=300)
    result = llm_summary(
        client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
    )
    assert result == SuccessResult(
        summary_text="这是一段摘要",
        response_id="resp_123",
        response_model=TEST_MODEL,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        elapsed_seconds=2.5,
    )
    client.responses.create.assert_called_once_with(
        model=TEST_MODEL,
        instructions=(
            "请将输入的对话总结为一段简洁、准确的摘要。"
            "重点保留核心讨论内容、关键结论和重要事实。"
            "不得添加原文中不存在的信息。"
            "只返回摘要正文，不要返回 JSON、字段描述或其他解释。"
        ),
        input="什么是过拟合?",
        max_output_tokens=300,
        store=False,
    )


def test_sdk_error_propagates() -> None:
    client = Mock()

    request = httpx2.Request(
        "POST",
        "https://api.deepseek.com/responses",
    )

    sdk_error = openai.APIConnectionError(
        request=request,
    )

    client.responses.create.side_effect = sdk_error

    settings = SummarySettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    with pytest.raises(openai.APIConnectionError) as exc_info:
        llm_summary(
            client=client,
            text="text",
            summary_settings=settings,
        )

    assert exc_info.value is sdk_error


def test_success_log_contains_metadata_and_no_sensitive_data(caplog) -> None:
    input_marker = "SENSITIVE_INPUT_123"
    output_marker = "SENSITIVE_OUTPUT_456"
    api_key_marker = "SENSITIVE_API_KEY_789"

    response = SimpleNamespace(
        status="completed",
        output_text=output_marker,
        id="resp_123",
        model=TEST_MODEL,
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
    )

    client = Mock()
    client.api_key = api_key_marker
    client.responses.create.return_value = response

    clock = Mock(side_effect=[10.0, 12.5])

    settings = SummarySettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    with caplog.at_level(logging.INFO):
        llm_summary(
            client=client,
            text=input_marker,
            summary_settings=settings,
            clock=clock,
        )

    assert len(caplog.records) == 1

    record = caplog.records[0]

    assert record.levelno == logging.INFO

    message = record.getMessage()

    assert f"model={TEST_MODEL}" in message
    assert "response_id=resp_123" in message
    assert "input_tokens=10" in message
    assert "output_tokens=5" in message
    assert "total_tokens=15" in message
    assert "elapsed_seconds=2.500000" in message

    assert input_marker not in message
    assert output_marker not in message
    assert api_key_marker not in message


def test_failure_log_contains_metadata_and_no_sensitive_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    input_marker = "SENSITIVE_INPUT_123"
    output_marker = "SENSITIVE_OUTPUT_456"
    api_key_marker = "SENSITIVE_API_KEY_789"

    response = SimpleNamespace(
        status="incomplete",
        output_text=output_marker,
        id="resp_safe_123",
        model=TEST_MODEL,
        usage=None,
    )

    client = Mock()
    client.api_key = api_key_marker
    client.responses.create.return_value = response

    settings = SummarySettings(
        model=TEST_MODEL,
        max_output_tokens=300,
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(LLMError):
            llm_summary(
                client=client,
                text=input_marker,
                summary_settings=settings,
            )

    # 1. 确实只产生一条预期日志
    assert len(caplog.records) == 1

    record = caplog.records[0]

    # 2. 日志级别正确
    assert record.levelno == logging.ERROR

    message = record.getMessage()

    # 3. 必要的失败元数据存在
    assert "status=incomplete" in message
    assert "response_id=resp_safe_123" in message

    # 4. 敏感内容没有泄露
    assert input_marker not in message
    assert output_marker not in message
    assert api_key_marker not in message


@pytest.mark.integration
def test_real_deepseek_smoke() -> None:
    run_smoke = os.getenv("RUN_DEEPSEEK_SMOKE")

    if run_smoke != "1":
        pytest.skip("真实 DeepSeek 冒烟测试未显式开启")

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

    settings = SummarySettings(
        model=model,
        max_output_tokens=2000,
    )

    result = llm_summary(
        client=client,
        text=(
            "用户：什么是过拟合？\n"
            "助手：过拟合是模型在训练数据上表现很好，"
            "但在未见数据上泛化能力较差的现象。"
        ),
        summary_settings=settings,
    )

    print("\n--- DeepSeek smoke test result ---")
    print(f"model: {result.response_model}")
    print(f"response_id: {result.response_id}")
    print(f"input_tokens: {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"total_tokens: {result.total_tokens}")
    print(f"elapsed_seconds: {result.elapsed_seconds:.6f}")

    assert result.summary_text.strip()
    assert result.response_id
    assert result.response_model
    assert result.input_tokens is not None
    assert result.output_tokens is not None
    assert result.total_tokens is not None
    assert result.elapsed_seconds >= 0
