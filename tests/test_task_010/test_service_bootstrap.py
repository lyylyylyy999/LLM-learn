import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from exercises.task_010_service_bootstrap import service_bootstrap as bootstrap


def set_valid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-task-010-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test-model")
    monkeypatch.delenv("DEEPSEEK_MAX_OUTPUT_TOKENS", raising=False)


def fake_client_with_completed_response() -> Mock:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "summary": "讨论了接口装配。",
                "key_points": ["模型调用经过现有分析函数"],
                "action_items": [],
            }
        ),
        id="resp-task-010",
        model="deepseek-test-model",
        usage=SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
            total_tokens=18,
        ),
    )
    return client


def test_module_import_does_not_require_config_or_create_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    client_factory = Mock(side_effect=AssertionError("client created during import"))
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    importlib.reload(bootstrap)

    client_factory.assert_not_called()


@pytest.mark.parametrize(
    ("missing_name", "replacement"),
    [
        ("DEEPSEEK_API_KEY", None),
        ("DEEPSEEK_API_KEY", " \t "),
        ("DEEPSEEK_MODEL", None),
        ("DEEPSEEK_MODEL", " \t "),
    ],
    ids=["missing-key", "blank-key", "missing-model", "blank-model"],
)
def test_invalid_required_config_fails_during_app_creation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    missing_name: str,
    replacement: str | None,
) -> None:
    set_valid_config(monkeypatch)
    if replacement is None:
        monkeypatch.delenv(missing_name)
    else:
        monkeypatch.setenv(missing_name, replacement)
    client_factory = Mock(side_effect=AssertionError("invalid config reached client"))
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    with pytest.raises(Exception) as exc_info:
        bootstrap.create_api_app()

    assert not isinstance(exc_info.value, KeyError)
    assert missing_name in str(exc_info.value)
    assert "sk-task-010-test-key" not in str(exc_info.value)
    assert "sk-task-010-test-key" not in caplog.text
    client_factory.assert_not_called()


@pytest.mark.parametrize("invalid_value", ["", "abc", "15"])
def test_invalid_token_limit_fails_during_app_creation(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    set_valid_config(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", invalid_value)
    client_factory = Mock(side_effect=AssertionError("invalid config reached client"))
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    with pytest.raises(Exception) as exc_info:
        bootstrap.create_api_app()

    assert "DEEPSEEK_MAX_OUTPUT_TOKENS" in str(exc_info.value)
    assert "sk-task-010-test-key" not in str(exc_info.value)
    client_factory.assert_not_called()


@pytest.mark.parametrize(
    ("configured_limit", "expected_limit"),
    [(None, 2000), ("16", 16), ("64", 64)],
    ids=["default", "lower-bound", "configured"],
)
def test_valid_post_uses_existing_analysis_chain_without_network(
    monkeypatch: pytest.MonkeyPatch,
    configured_limit: str | None,
    expected_limit: int,
) -> None:
    set_valid_config(monkeypatch)
    if configured_limit is not None:
        monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", configured_limit)
    fake_client = fake_client_with_completed_response()
    client_factory = Mock(return_value=fake_client)
    monkeypatch.setattr(bootstrap.openai, "OpenAI", client_factory)

    app = bootstrap.create_api_app()

    fake_client.responses.create.assert_not_called()

    response = TestClient(app).post(
        "/analyses",
        json={"conversation": "  测试对话  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis"] == {
        "summary": "讨论了接口装配。",
        "key_points": ["模型调用经过现有分析函数"],
        "action_items": [],
    }
    assert body["response_id"] == "resp-task-010"
    assert body["model"] == "deepseek-test-model"
    assert body["input_tokens"] == 11
    assert body["output_tokens"] == 7
    assert body["total_tokens"] == 18
    client_factory.assert_called_once_with(
        api_key="sk-task-010-test-key",
        base_url="https://api.deepseek.com",
    )
    fake_client.responses.create.assert_called_once()
    call_kwargs = fake_client.responses.create.call_args.kwargs
    assert call_kwargs["input"] == "测试对话"
    assert call_kwargs["model"] == "deepseek-test-model"
    assert call_kwargs["max_output_tokens"] == expected_limit


def test_invalid_post_is_rejected_before_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_config(monkeypatch)
    fake_client = fake_client_with_completed_response()
    monkeypatch.setattr(bootstrap.openai, "OpenAI", Mock(return_value=fake_client))
    app = bootstrap.create_api_app()
    client = TestClient(app)

    response = client.post("/analyses", json={"conversation": " \t "})

    assert response.status_code == 422
    fake_client.responses.create.assert_not_called()


def test_app_keeps_post_only_analysis_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_config(monkeypatch)
    fake_client = fake_client_with_completed_response()
    monkeypatch.setattr(bootstrap.openai, "OpenAI", Mock(return_value=fake_client))
    app = bootstrap.create_api_app()
    client = TestClient(app)

    response = client.get("/analyses", params={"conversation": "测试对话"})

    assert response.status_code == 405
    fake_client.responses.create.assert_not_called()
    assert "post" in app.openapi()["paths"]["/analyses"]
    assert "get" not in app.openapi()["paths"]["/analyses"]
