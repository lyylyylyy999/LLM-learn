from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from exercises.task_007_structured_analysis.structured_analysis import (
    AnalysisResponse,
    AnalysisResult,
    LLMError,
    StructuredOutputError,
)
from exercises.task_009_fastapi_analysis.fastapi_analysis import create_app


@dataclass
class RecordingAnalyzer:
    response: AnalysisResponse | None = None
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def __call__(self, conversation: str) -> AnalysisResponse:
        self.calls.append(conversation)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def make_analysis_response(
    *,
    input_tokens: int | None = 12,
    output_tokens: int | None = 8,
    total_tokens: int | None = 20,
) -> AnalysisResponse:
    return AnalysisResponse(
        analysis=AnalysisResult(
            summary="讨论了如何测试 FastAPI 接口。",
            key_points=["使用依赖替身隔离真实模型"],
            action_items=[],
        ),
        response_id="resp-task-009",
        model="deepseek-test",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_seconds=0.25,
    )


def test_success_returns_complete_response_and_calls_analyzer_once() -> None:
    analyzer = RecordingAnalyzer(response=make_analysis_response())
    client = TestClient(create_app(analyzer))

    response = client.post(
        "/analyses",
        json={"conversation": "  请分析这段对话。  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "analysis": {
            "summary": "讨论了如何测试 FastAPI 接口。",
            "key_points": ["使用依赖替身隔离真实模型"],
            "action_items": [],
        },
        "response_id": "resp-task-009",
        "model": "deepseek-test",
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
        "elapsed_seconds": 0.25,
    }
    assert analyzer.calls == ["请分析这段对话。"]


def test_success_preserves_nullable_token_usage() -> None:
    analyzer = RecordingAnalyzer(
        response=make_analysis_response(
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
    )
    client = TestClient(create_app(analyzer))

    response = client.post("/analyses", json={"conversation": "有效对话"})

    assert response.status_code == 200
    body = response.json()
    assert body["input_tokens"] is None
    assert body["output_tokens"] is None
    assert body["total_tokens"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"conversation": None},
        {"conversation": 123},
        {"conversation": ""},
        {"conversation": " \t\n "},
        {"conversation": "有效对话", "unexpected": "field"},
    ],
    ids=[
        "missing",
        "null",
        "wrong-type",
        "empty",
        "whitespace-only",
        "extra-field",
    ],
)
def test_invalid_request_returns_422_without_calling_analyzer(
    payload: dict[str, object],
) -> None:
    analyzer = RecordingAnalyzer(response=make_analysis_response())
    client = TestClient(create_app(analyzer))

    response = client.post("/analyses", json=payload)

    assert response.status_code == 422
    assert analyzer.calls == []


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            LLMError("模型失败：sk-task-009-secret；原始对话：不要泄露"),
            "llm_response_error",
        ),
        (
            StructuredOutputError(
                "解析失败：sk-task-009-secret；原始输出：不要泄露"
            ),
            "structured_output_error",
        ),
    ],
)
def test_known_model_error_returns_safe_structured_502(
    error: Exception,
    expected_code: str,
) -> None:
    analyzer = RecordingAnalyzer(error=error)
    client = TestClient(create_app(analyzer))

    response = client.post(
        "/analyses",
        json={"conversation": "敏感对话标记-task-009"},
    )

    assert response.status_code == 502
    body = response.json()
    assert isinstance(body, dict)
    detail = body.get("detail", body)
    assert isinstance(detail, dict)
    assert detail.get("code") == expected_code
    message = detail.get("message")
    assert isinstance(message, str)
    assert message.strip() != ""

    serialized_body = response.text
    assert "sk-task-009-secret" not in serialized_body
    assert "不要泄露" not in serialized_body
    assert "敏感对话标记-task-009" not in serialized_body
    assert analyzer.calls == ["敏感对话标记-task-009"]


def test_unexpected_error_is_not_misclassified_as_known_model_error() -> None:
    analyzer = RecordingAnalyzer(error=RuntimeError("unexpected defect"))
    client = TestClient(create_app(analyzer))

    with pytest.raises(RuntimeError, match="unexpected defect"):
        client.post("/analyses", json={"conversation": "有效对话"})

    assert analyzer.calls == ["有效对话"]


def test_openapi_describes_request_and_success_response_models() -> None:
    analyzer = RecordingAnalyzer(response=make_analysis_response())
    schema = create_app(analyzer).openapi()

    operation = schema["paths"]["/analyses"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert request_schema["$ref"].endswith("/AnalysisRequest")
    assert response_schema["$ref"].endswith("/AnalysisResponse")

