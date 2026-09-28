from typing import Annotated, Protocol

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from exercises.task_007_structured_analysis.structured_analysis import (
    AnalysisResponse,
    LLMError,
    StructuredOutputError,
)

NonBlankStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"\S",
    ),
]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: NonBlankStr


class Analyzer(Protocol):
    def __call__(self, conversation: str) -> AnalysisResponse: ...


def create_app(analyzer: Analyzer) -> FastAPI:
    app = FastAPI()

    @app.post("/analyses", response_model=AnalysisResponse)
    def analyze(request: AnalysisRequest) -> AnalysisResponse:
        try:
            return analyzer(request.conversation)
        except LLMError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "llm_response_error",
                    "message": "这是大模型响应错误",
                },
            )
        except StructuredOutputError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "structured_output_error",
                    "message": "这是数据校验失败",
                },
            )

    return app
