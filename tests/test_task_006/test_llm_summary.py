import logging
import pytest
import httpx
import openai
from exercises.task_006_llm_summary.llm_summary import (
    llm_summary,
    SuccessResult,
    SummarySettings,
    LLMError,
)
from types import SimpleNamespace
from unittest.mock import Mock


def test_normal_response() -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text="这是一段摘要",
        id="resp_123",
        model="deepseek-flash",
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model="deepseek_flash", max_output_tokens=16)
    result = llm_summary(
        client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
    )
    assert result == SuccessResult(
        summary_text="这是一段摘要",
        response_id="resp_123",
        response_model="deepseek-flash",
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        elapsed_seconds=2.5,
    )
    client.responses.create.assert_called_once_with(
        model="deepseek_flash",
        instructions="摘要目标是获得 SuccessResult 数据结构，不添加原文不存在的信息",
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


@pytest.mark.parametrize(
        ("text"),
        [
            (""),
            ("  "),
            ("\n")
        ]
)
def test_empty_text(text: str) -> None:
    client = Mock()
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model="deepseek_flash", max_output_tokens=300)
    with pytest.raises(ValueError, match="拒绝空字符串或纯空白对话"):
        llm_summary(client=client, text=text, summary_settings=settings, clock=clock)


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
        model="deepseek-flash",
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model="deepseek_flash", max_output_tokens=300)
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
        model="deepseek-flash",
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        ),
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model="deepseek_flash", max_output_tokens=300)
    with pytest.raises(exception, match="发生异常，响应 ID: resp_123,状态: completed"):
        llm_summary(
            client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
        )


def test_usage_is_None() -> None:
    fake_response = SimpleNamespace(
        status="completed",
        output_text="这是一段摘要",
        id="resp_123",
        model="deepseek-flash",
        usage=None,
    )
    client = Mock()
    client.responses.create.return_value = fake_response
    clock = Mock(side_effect=[10.0, 12.5])
    settings = SummarySettings(model="deepseek_flash", max_output_tokens=300)
    result = llm_summary(
        client=client, text="什么是过拟合?", summary_settings=settings, clock=clock
    )
    assert result == SuccessResult(
        summary_text="这是一段摘要",
        response_id="resp_123",
        response_model="deepseek-flash",
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        elapsed_seconds=2.5,
    )
    client.responses.create.assert_called_once_with(
        model="deepseek_flash",
        instructions="摘要目标是获得 SuccessResult 数据结构，不添加原文不存在的信息",
        input="什么是过拟合?",
        max_output_tokens=300,
        store=False,
    )


def test_sdk_error_propagates() -> None:
    client = Mock()

    request = httpx.Request(
        "POST",
        "https://api.deepseek.com/responses",
    )

    sdk_error = openai.APIConnectionError(
        request=request,
    )

    client.responses.create.side_effect = sdk_error

    settings = SummarySettings(
        model="deepseek-flash",
        max_output_tokens=300,
    )

    with pytest.raises(openai.APIConnectionError) as exc_info:
        llm_summary(
            client=client,
            text="text",
            summary_settings=settings,
        )

    assert exc_info.value is sdk_error


def test_success_log_does_not_leak_sensitive_data(caplog) -> None:
    input_marker = "SENSITIVE_INPUT_7f3a9c"
    output_marker = "SENSITIVE_OUTPUT_8b4d2e"
    api_key_marker = "SENSITIVE_API_KEY_1c6f5a"

    response = SimpleNamespace(
        status="completed",
        output_text=output_marker,
        id="resp_123",
        model="deepseek-flash",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
    )

    client = Mock()
    client.api_key = api_key_marker
    client.responses.create.return_value = response

    settings = SummarySettings(
        model="deepseek-flash",
        max_output_tokens=300,
    )

    clock = Mock(side_effect=[10.0, 12.5])

    with caplog.at_level(logging.INFO):
        llm_summary(
            client=client,
            text=input_marker,
            summary_settings=settings,
            clock=clock,
        )

    log_text = caplog.text

    assert input_marker not in log_text
    assert output_marker not in log_text
    assert api_key_marker not in log_text


def test_failure_does_not_leak_sensitive_data(caplog) -> None:
    input_marker = "SENSITIVE_INPUT_a81f23"
    output_marker = "SENSITIVE_OUTPUT_b72c91"
    api_key_marker = "SENSITIVE_API_KEY_c93d47"

    response = SimpleNamespace(
        status="incomplete",
        output_text=output_marker,
        id="resp_safe_id",
        model="deepseek-flash",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
        ),
    )

    client = Mock()
    client.api_key = api_key_marker
    client.responses.create.return_value = response

    settings = SummarySettings(
        model="deepseek-flash",
        max_output_tokens=300,
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(LLMError) as exc_info:
            llm_summary(
                client=client,
                text=input_marker,
                summary_settings=settings,
            )

    log_text = caplog.text
    exception_text = str(exc_info.value)

    for secret in (
        input_marker,
        output_marker,
        api_key_marker,
    ):
        assert secret not in log_text
        assert secret not in exception_text


import os

import pytest
from openai import OpenAI

from exercises.task_006_llm_summary.llm_summary import (
    SummarySettings,
    llm_summary,
)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DEEPSEEK_SMOKE") != "1",
    reason="真实 DeepSeek 冒烟测试默认关闭",
)
def test_real_deepseek_smoke() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    model = os.environ.get("DEEPSEEK_SMOKE_MODEL", "deepseek-flash")

    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY 未设置")

    client = OpenAI(
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
            "但在未见数据上泛化能力较差的现象。\n"
            "用户：如何缓解？\n"
            "助手：可以使用正则化、增加数据和交叉验证。"
        ),
        summary_settings=settings,
    )

    assert result.summary_text.strip()
    assert result.response_id
    assert result.response_model
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert result.total_tokens > 0
    assert result.elapsed_seconds >= 0
