from dataclasses import FrozenInstanceError
from typing import Any, cast
from unittest.mock import Mock

import pytest

from exercises.task_004_request_trace.request_trace import RequestTrace, TraceRecord


def test_normal_record() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.00, 11.00])
    trace = RequestTrace(request_name="test_normal", sink=sink, clock=clock)
    assert trace.record is None
    assert sink.call_count == 0
    with trace:
        assert trace.record is None
        assert sink.call_count == 0
    record = trace.record
    assert record is not None
    assert record.request_name == "test_normal"
    assert record.elapsed_seconds == pytest.approx(1.00)
    assert record.status == "success"
    assert record.error_type is None
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_abnormal_record() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.00, 11.00])
    trace = RequestTrace(request_name="test_abnormal", sink=sink, clock=clock)
    original = ValueError("test_abnormal_record")
    with pytest.raises(ValueError, match="test_abnormal_record") as exc_info, trace:
        raise original

    assert exc_info.value is original
    record = trace.record
    assert record is not None
    assert record.request_name == "test_abnormal"
    assert record.elapsed_seconds == pytest.approx(1.00)
    assert record.status == "failure"
    assert record.error_type == "ValueError"
    assert sink.call_count == 1
    sent = sink.call_args.args[0]
    assert sent is trace.record
    assert clock.call_count == 2


@pytest.mark.parametrize(
    ("request_name", "exception", "match"),
    [
        ("", ValueError, "request_name 只能是非空字符串类型"),
        ("  ", ValueError, "request_name 只能是非空字符串类型"),
        ("\n", ValueError, "request_name 只能是非空字符串类型"),
        ("\t", ValueError, "request_name 只能是非空字符串类型"),
        (123, ValueError, "request_name 只能是非空字符串类型"),
    ],
)
def test_invalid_request_name(
    request_name: str, exception: type[Exception], match: str
) -> None:
    sink = Mock()
    clock = Mock(side_effect=[10, 11])
    with pytest.raises(exception, match=match):
        RequestTrace(request_name=request_name, sink=sink, clock=clock)
    assert sink.call_count == 0
    assert clock.call_count == 0


def test_enter_returns_same_instance() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.0, 10.25])

    trace = RequestTrace(
        request_name="get_user",
        sink=sink,
        clock=clock,
    )

    with trace as entered:
        assert entered is trace


def test_same_instance_used_twice_sequentially() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10, 11])
    trace = RequestTrace(request_name="test", sink=sink, clock=clock)
    with pytest.raises(
        RuntimeError, match="RequestTrace instance can only be entered once"
    ):
        with trace:
            pass
        first_record = trace.record
        with trace:
            pass
    assert first_record is trace.record
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_same_instance_used_nested() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10, 11])
    trace = RequestTrace(request_name="test", sink=sink, clock=clock)
    with (
        pytest.raises(
            RuntimeError, match="RequestTrace instance can only be entered once"
        ),
        trace,
        trace,
    ):
        pass
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_two_instances_are_independent() -> None:
    sink1 = Mock()
    sink2 = Mock()

    clock1 = Mock(side_effect=[10.0, 10.25])
    clock2 = Mock(side_effect=[20.0, 20.5])

    trace1 = RequestTrace(
        request_name="request_1",
        sink=sink1,
        clock=clock1,
    )

    trace2 = RequestTrace(
        request_name="request_2",
        sink=sink2,
        clock=clock2,
    )

    with trace1:
        pass

    with trace2:
        pass

    assert trace1.record is not None
    assert trace2.record is not None

    assert trace1.record.request_name == "request_1"
    assert trace2.record.request_name == "request_2"

    assert trace1.record.elapsed_seconds == pytest.approx(0.25)
    assert trace2.record.elapsed_seconds == pytest.approx(0.5)

    assert sink1.call_count == 1
    assert sink2.call_count == 1

    with pytest.raises(RuntimeError), trace1:
        pass

    with pytest.raises(RuntimeError), trace2:
        pass


def test_same_clock() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.00, 10.00])
    trace = RequestTrace(request_name="test_normal", sink=sink, clock=clock)
    with trace:
        pass
    record = trace.record
    assert record is not None
    assert record.request_name == "test_normal"
    assert record.elapsed_seconds == 0
    assert record.status == "success"
    assert record.error_type is None
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_no_message_exception() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.00, 11.00])
    trace = RequestTrace(request_name="test", sink=sink, clock=clock)
    with pytest.raises(ValueError, match=None), trace:
        raise ValueError
    record = trace.record
    assert record is not None
    assert record.request_name == "test"
    assert record.elapsed_seconds == pytest.approx(1.00)
    assert record.status == "failure"
    assert record.error_type == "ValueError"
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_trace_record_is_frozen() -> None:
    record = TraceRecord(
        request_name="get_user",
        status="success",
        elapsed_seconds=0.25,
        error_type=None,
    )

    with pytest.raises(FrozenInstanceError):
        cast(Any, record).status = "failure"
