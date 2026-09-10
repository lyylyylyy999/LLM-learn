import pytest
from exercises.task_004_request_trace.request_trace import RequestTrace
from unittest.mock import Mock


def test_normal_record() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10.00, 11.00])
    trace = RequestTrace(request_name="test_normal", sink=sink, clock=clock)
    assert trace.record is None
    assert sink.call_count == 0
    with trace:
        pass
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
    with pytest.raises(ValueError, match="test_abnormal_record"):
        with trace:
            raise ValueError("test_abnormal_record")
    record = trace.record
    assert record is not None
    assert record.request_name == "test_abnormal"
    assert record.elapsed_seconds == pytest.approx(1.00)
    assert record.status == "fail"
    assert record.error_type == "ValueError"
    assert sink.call_count == 1
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
    trace = RequestTrace(request_name=request_name, sink=sink, clock=clock)
    with pytest.raises(exception, match=match):
        with trace:
            pass
    sink.call_count == 0
    clock.call_count == 0


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
        with trace:
            pass
    assert sink.call_count == 1
    assert clock.call_count == 2


def test_same_instance_used_nested() -> None:
    sink = Mock()
    clock = Mock(side_effect=[10, 11])
    trace = RequestTrace(request_name="test", sink=sink, clock=clock)
    with pytest.raises(
        RuntimeError, match="RequestTrace instance can only be entered once"
    ):
        with trace:
            with trace:
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

    # trace1 已经用过，但不应该影响 trace2
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

    # trace1 自己仍然不能再次进入
    with pytest.raises(RuntimeError):
        with trace1:
            pass

    # trace2 自己也不能再次进入
    with pytest.raises(RuntimeError):
        with trace2:
            pass
