import time
from dataclasses import dataclass
from typing import Literal, Callable


@dataclass
class TraceRecord:
    request_name: str
    status: Literal["success", "fail"]
    elapsed_seconds: float
    error_type: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.request_name, str) or not self.request_name.strip():
            raise ValueError("request_name 只能是非空字符串类型")


class RequestTrace:
    def __init__(
        self,
        request_name: str,
        sink: Callable[[TraceRecord], None],
        clock: Callable[[], float] = time.perf_counter,
    ):
        self.request_name = request_name
        self.clock = clock
        self.sink = sink
        self._record: TraceRecord | None = None
        self._entered = False
        self.start: float | None = None

    @property
    def record(self) -> TraceRecord | None:
        return self._record

    def __enter__(self):
        if self._entered:
            raise RuntimeError("RequestTrace instance can only be entered once")

        self._entered = True
        self.start = self.clock()
        return self

    def __exit__(self, exc_type, exc, tb):
        end = self.clock()
        self.time = end - self.start
        self._record = TraceRecord(
            request_name=self.request_name,
            status="success" if exc_type is None else "fail",
            elapsed_seconds=self.time,
            error_type=None if exc_type is None else exc_type.__name__,
        )
        self.sink(self._record)
        return False
