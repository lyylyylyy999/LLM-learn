import pytest
from exercises.task_002_retry_executor.retry_decorator import retry
from exercises.task_002_retry_executor.sync_retry_executor import (
    RetryPolicy,
    RetryExhaustedError,
)
from unittest.mock import Mock, call


def test_no_parameter() -> None:
    mock = Mock(side_effect=["ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    assert operation() == "ok"
    assert mock.call_count == 1
    assert sleep_mock.call_args_list == []


def test_with_parameter() -> None:
    mock = Mock(side_effect=[TimeoutError, ConnectionError, "ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=2)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation(a: int, b: int, flag: bool = True):
        return mock(a, b, flag=flag)

    result = operation(10, 20, flag=False)
    assert result == "ok"
    assert mock.call_args_list == [
        call(10, 20, flag=False),
        call(10, 20, flag=False),
        call(10, 20, flag=False),
    ]
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


def test_non_retryable_exception() -> None:
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
    assert mock.call_count == 1
    assert sleep_mock.call_count == 0


def test_returns_operation_result() -> None:
    input_list = ["ok"]
    mock = Mock(return_value=input_list)
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation() -> list[str]:
        return mock()

    result = operation()
    assert input_list is result


def test_state_with_decorator() -> None:
    mock = Mock(side_effect=[TimeoutError, "ok", "hello"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=2)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation():
        return mock()

    result1 = operation()
    result2 = operation()
    assert result1 == "ok"
    assert result2 == "hello"
    assert mock.call_count == 3
    assert sleep_mock.call_args_list == [call(policy.delay_seconds)]


def test_wrapped_points_to_original_function() -> None:
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    def operation() -> str:
        """测试文档"""
        return "ok"

    original = operation

    decorated = retry(
        policy=policy,
        sleep_func=sleep_mock,
    )(operation)

    assert decorated.__name__ == "operation"
    assert decorated.__doc__ == "测试文档"
    assert getattr(decorated, "__wrapped__") is original


def test_decorated_instance_method_can_access_self_state() -> None:
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    class Counter:
        def __init__(self) -> None:
            self.value = 10

        @retry(policy=policy, sleep_func=sleep_mock)
        def add(self, amount: int) -> int:
            self.value += amount
            return self.value

    counter = Counter()

    result = counter.add(5)

    assert result == 15
    assert counter.value == 15


def test_same_policy_can_be_reused_without_mutation() -> None:
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)
    original_max_attempts = policy.max_attempts
    original_delay_seconds = policy.delay_seconds
    original_retryable_exceptions = policy.retryable_exceptions

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation1():
        return "one"

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation2():
        return "two"

    assert operation1() == "one"
    assert operation2() == "two"
    assert policy.max_attempts == original_max_attempts
    assert policy.delay_seconds == original_delay_seconds
    assert policy.retryable_exceptions == original_retryable_exceptions


def test_decorated_function_can_return_none() -> None:
    sleep_mock = Mock()
    mock = Mock(return_value=None)

    policy = RetryPolicy(
        max_attempts=3,
        delay_seconds=1,
    )

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation() -> None:
        return mock()

    result = operation()

    assert result is None
    assert mock.call_count == 1
    sleep_mock.assert_not_called()


def test_mutable_input_is_not_modified_and_identity_is_preserved() -> None:
    input_list = ["a", "b"]
    original_content = input_list.copy()

    mock = Mock(
        side_effect=[
            TimeoutError(),
            "ok",
        ]
    )
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=3, delay_seconds=1)

    @retry(policy=policy, sleep_func=sleep_mock)
    def operation(values: list[str]) -> str:
        return mock(values)

    result = operation(input_list)

    assert result == "ok"
    assert input_list == original_content
    assert mock.call_count == 2
    assert mock.call_args_list[0].args[0] is input_list
    assert mock.call_args_list[1].args[0] is input_list
