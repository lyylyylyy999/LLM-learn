import traceback
from unittest.mock import Mock

import openai
import pytest
from fastapi.testclient import TestClient

from exercises.task_007_structured_analysis.structured_analysis import (
    AnalysisSettings,
    LLMError,
    LLMTimeoutError,
    structured_analysis,
)
from exercises.task_010_service_bootstrap import service_bootstrap as bootstrap


def set_valid_config(
    monkeypatch: pytest.MonkeyPatch,
    *,
    timeout: str | None = None,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-task-011-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test-model")
    monkeypatch.delenv("DEEPSEEK_MAX_OUTPUT_TOKENS", raising=False)
    if timeout is None:
        monkeypatch.delenv("DEEPSEEK_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", timeout)


def make_timeout_error(sensitive_detail: str) -> openai.APITimeoutError:
    error = openai.APITimeoutError(request=Mock())
    error.args = (sensitive_detail,)
    return error


@pytest.mark.parametrize(
    ("configured_timeout", "expected_timeout"),
    [
        (None, 30.0),
        ("0.25", 0.25),
        (" 12.5 ", 12.5),
    ],
    ids=["default", "fractional", "surrounding-whitespace"],
)
def test_valid_timeout_configures_client_without_model_call(
    monkeypatch: pytest.MonkeyPatch,
    configured_timeout: str | None,
    expected_timeout: float,
) -> None:
    set_valid_config(monkeypatch, timeout=configured_timeout)
    fake_client = Mock()
    client_factory = Mock(return_value=fake_client)
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    app = bootstrap.create_api_app()

    assert app is not None
    client_factory.assert_called_once_with(
        api_key="sk-task-011-test-key",
        base_url="https://api.deepseek.com",
        timeout=expected_timeout,
        max_retries=0,
    )
    fake_client.responses.create.assert_not_called()


@pytest.mark.parametrize(
    "invalid_timeout",
    ["", "not-a-number", "0", "-0.5", "nan", "inf", "-inf"],
    ids=["empty", "non-number", "zero", "negative", "nan", "inf", "negative-inf"],
)
def test_invalid_timeout_fails_before_client_creation(
    monkeypatch: pytest.MonkeyPatch,
    invalid_timeout: str,
) -> None:
    set_valid_config(monkeypatch, timeout=invalid_timeout)
    client_factory = Mock(side_effect=AssertionError("client must not be created"))
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    with pytest.raises(ValueError) as exc_info:
        bootstrap.create_api_app()

    assert "DEEPSEEK_TIMEOUT_SECONDS" in str(exc_info.value)
    if invalid_timeout:
        assert invalid_timeout not in str(exc_info.value)
    client_factory.assert_not_called()


def test_invalid_timeout_value_is_absent_from_traceback_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_value = "sk-task-011-misplaced-secret"
    set_valid_config(monkeypatch, timeout=sensitive_value)
    client_factory = Mock(side_effect=AssertionError("client must not be created"))
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    with pytest.raises(ValueError) as exc_info:
        bootstrap.create_api_app()

    formatted_traceback = "".join(traceback.format_exception(exc_info.value))
    assert "DEEPSEEK_TIMEOUT_SECONDS" in formatted_traceback
    assert sensitive_value not in formatted_traceback
    assert sensitive_value not in caplog.text
    client_factory.assert_not_called()


def test_sdk_timeout_becomes_domain_timeout_and_preserves_cause() -> None:
    sensitive_sdk_detail = "sdk-timeout-secret-task-011"
    timeout_error = make_timeout_error(sensitive_sdk_detail)
    client = Mock()
    client.responses.create.side_effect = timeout_error
    settings = AnalysisSettings(model="deepseek-test-model", max_output_tokens=64)

    with pytest.raises(LLMTimeoutError) as exc_info:
        structured_analysis(
            client=client,
            input="sensitive-conversation-task-011",
            settings=settings,
        )

    assert exc_info.value.__cause__ is timeout_error
    assert isinstance(exc_info.value, LLMError)
    assert sensitive_sdk_detail not in str(exc_info.value)
    assert "sensitive-conversation-task-011" not in str(exc_info.value)
    client.responses.create.assert_called_once()


def test_timeout_returns_safe_504_through_complete_offline_chain(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_conversation = "sensitive-conversation-task-011"
    sensitive_sdk_detail = "sdk-timeout-secret-task-011"
    set_valid_config(monkeypatch)
    fake_client = Mock()
    fake_client.responses.create.side_effect = make_timeout_error(sensitive_sdk_detail)
    monkeypatch.setattr(bootstrap.openai, "OpenAI", Mock(return_value=fake_client))

    response = TestClient(bootstrap.create_api_app()).post(
        "/analyses",
        json={"conversation": sensitive_conversation},
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "llm_timeout"
    message = response.json()["detail"]["message"]
    assert isinstance(message, str)
    assert message.strip()
    assert sensitive_conversation not in response.text
    assert sensitive_sdk_detail not in response.text
    assert sensitive_conversation not in caplog.text
    assert sensitive_sdk_detail not in caplog.text
    fake_client.responses.create.assert_called_once()
    assert (
        fake_client.responses.create.call_args.kwargs["input"] == sensitive_conversation
    )


def test_non_timeout_sdk_error_is_not_misclassified() -> None:
    connection_error = openai.APIConnectionError(
        message="connection-secret-task-011",
        request=Mock(),
    )
    client = Mock()
    client.responses.create.side_effect = connection_error
    settings = AnalysisSettings(model="deepseek-test-model", max_output_tokens=64)

    with pytest.raises(openai.APIConnectionError) as exc_info:
        structured_analysis(
            client=client,
            input="测试对话",
            settings=settings,
        )

    assert exc_info.value is connection_error
    client.responses.create.assert_called_once()


def test_invalid_http_input_does_not_reach_timeout_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_config(monkeypatch)
    fake_client = Mock()
    fake_client.responses.create.side_effect = make_timeout_error("unused-timeout")
    monkeypatch.setattr(bootstrap.openai, "OpenAI", Mock(return_value=fake_client))
    client = TestClient(bootstrap.create_api_app())

    response = client.post("/analyses", json={"conversation": " \t "})

    assert response.status_code == 422
    fake_client.responses.create.assert_not_called()
