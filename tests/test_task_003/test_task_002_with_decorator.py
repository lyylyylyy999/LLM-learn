import pytest
from exercises.task_002_retry_executor.sync_retry_executor import (
    retry,
    RetryPolicy,
    RetryExhaustedError,
)
from unittest.mock import Mock, call


def test_no_parameter() -> None:
    mock = Mock(side_effect=[TimeoutError, "ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    assert operation() == "ok"
    assert mock.call_count == 2
    assert sleep_mock.call_args_list == [call(policy.delay_seconds)]


def test_with_parameter() -> None:
    mock = Mock(side_effect=[TimeoutError, ConnectionError, "ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=2)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation(a: int, b: int, flag: bool = True):
        return mock(a, b, flag=flag)

    result = operation(10, 20, flag=False)
    assert result == "ok"
    assert mock.call_count == 3
    assert sleep_mock.call_args_list == [
        call(policy.delay_seconds),
        call(policy.delay_seconds),
    ]


def test_max_attempts() -> None:
    mock = Mock(side_effect=[TimeoutError, TimeoutError, ConnectionError])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    with pytest.raises(
        RetryExhaustedError, match="重试 3 次后仍然失败，最后一次异常为ConnectionError"
    ) as exc_info:
        operation()
    assert mock.call_count == 3
    assert sleep_mock.call_args_list == [
        call(policy.delay_seconds),
        call(policy.delay_seconds),
    ]
    err = exc_info.value
    assert err.attempts == 3
    assert isinstance(err.last_error, ConnectionError)
    assert str(err.last_error) == ""
    assert isinstance(err.__cause__, ConnectionError)
    assert str(err.__cause__) == ""


def test_no_allowed_exception() -> None:
    original_error = TypeError("类型错误")
    mock = Mock(side_effect=[original_error])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    with pytest.raises(TypeError, match="类型错误") as exc_info:
        operation()
    assert exc_info.value is original_error


def test_same_input_and_result() -> None:
    input = "ok"
    mock = Mock(side_effect=[input])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    result = operation()
    assert input is result


def test_state_with_decorator() -> None:
    mock1 = Mock(side_effect=[TimeoutError, "ok"])
    mock2 = Mock(side_effect=["ok"])
    sleep_mock_1 = Mock()
    sleep_mock_2 = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=2)

    @retry(policy=policy, sleep_func=sleep_mock_1)
    def operation1():
        return mock1()

    @retry(policy=policy, sleep_func=sleep_mock_2)
    def operation2():
        return mock2()

    result1 = operation1()
    result2 = operation2()
    assert result1 == "ok"
    assert result2 == "ok"
    assert mock1.call_count == 2
    assert mock2.call_count == 1
    assert sleep_mock_1.call_args_list == [call(policy.delay_seconds)]


def test_metadata_exist() -> None:
    mock = Mock(side_effect=["ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    assert operation.__name__ == "operation"
    assert operation.__doc__ is None
