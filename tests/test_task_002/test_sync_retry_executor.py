import pytest
import logging
from unittest.mock import Mock
from exercises.task_002_retry_executor.sync_retry_executor import (
    RetryExhaustedError,
    RetryPolicy,
    execute_with_retry,
)


def test_one_call_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    mock = Mock(side_effect=["ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=2)
    result = execute_with_retry(mock, policy, sleep_mock)
    assert result == "ok"
    assert len(caplog.records) == 1
    assert sleep_mock.call_count == 0


def test_fail_after_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    mock = Mock(side_effect=[TimeoutError("超时"), TimeoutError("超时"), "ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=5, delay_seconds=0)
    result = execute_with_retry(mock, policy, sleep_mock)
    assert mock.call_count == 3
    assert result == "ok"
    assert len(caplog.records) == 2
    warning_log = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert len(warning_log) == 2
    assert (
        "当前尝试次数为 1,最大尝试次数为 5,异常信息为超时"
        in caplog.records[0].getMessage()
    )
    assert (
        "当前尝试次数为 2,最大尝试次数为 5,异常信息为超时"
        in caplog.records[1].getMessage()
    )
    assert sleep_mock.call_count == 2


def test_all_fail(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    mock = Mock(
        side_effect=[
            TimeoutError("超时"),
            TimeoutError("超时"),
            ConnectionError("连接错误"),
            ConnectionError("连接错误"),
        ]
    )
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=4, delay_seconds=0)
    with pytest.raises(
        RetryExhaustedError, match="重试 4 次后仍然失败，最后一次异常：连接错误"
    ) as exc_info:
        execute_with_retry(mock, policy, sleep_mock)
    assert mock.call_count == 4
    assert len(caplog.records) == 4
    warning_log = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    error_log = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert len(warning_log) == 3
    assert len(error_log) == 1
    assert (
        "当前尝试次数为 1,最大尝试次数为 4,异常信息为超时"
        in caplog.records[0].getMessage()
    )
    assert (
        "当前尝试次数为 2,最大尝试次数为 4,异常信息为超时"
        in caplog.records[1].getMessage()
    )
    assert (
        "当前尝试次数为 3,最大尝试次数为 4,异常信息为连接错误"
        in caplog.records[2].getMessage()
    )
    assert (
        "当前已达到最大尝试次数 4,最后一次异常信息为连接错误"
        in caplog.records[3].getMessage()
    )
    err = exc_info.value
    assert err.attempts == 4
    assert isinstance(err.last_error, ConnectionError)
    assert str(err.last_error) == "连接错误"
    assert isinstance(err.__cause__, ConnectionError)
    assert str(err.__cause__) == "连接错误"
    assert sleep_mock.call_count == 3


def test_not_allowed_exception(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    mock = Mock(side_effect=[TimeoutError("超时"), TypeError("类型错误")])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=4, delay_seconds=0)
    with pytest.raises(TypeError, match="类型错误"):
        execute_with_retry(mock, policy, sleep_mock)
    assert mock.call_count == 2
    assert len(caplog.records) == 1
    warning_log = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert len(warning_log) == 1
    assert (
        "当前尝试次数为 1,最大尝试次数为 4,异常信息为超时"
        in caplog.records[0].getMessage()
    )
    assert sleep_mock.call_count == 1


def test_max_attempts_normal() -> None:
    mock = Mock(side_effect=["ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=1, delay_seconds=0)
    result = execute_with_retry(mock, policy, sleep_mock)
    assert result == "ok"
    assert mock.call_count == 1
    assert sleep_mock.call_count == 0


def test_same_object() -> None:
    mock = Mock()
    mock.return_value = mock
    policy = RetryPolicy(max_attempts=1, delay_seconds=0)
    result = execute_with_retry(mock, policy)
    assert result is mock
    assert mock.call_count == 1


def test_max_attempts_abnormal(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    mock = Mock(side_effect=[TimeoutError("超时"), "ok"])
    sleep_mock = Mock()
    policy = RetryPolicy(max_attempts=1, delay_seconds=0)
    with pytest.raises(
        RetryExhaustedError, match="重试 1 次后仍然失败，最后一次异常：超时"
    ) as exc_info:
        execute_with_retry(mock, policy, sleep_mock)
    assert mock.call_count == 1
    assert len(caplog.records) == 1
    error_log = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert len(error_log) == 1
    assert (
        "当前已达到最大尝试次数 1,最后一次异常信息为超时"
        in caplog.records[0].getMessage()
    )
    err = exc_info.value
    assert err.attempts == 1
    assert isinstance(err.last_error, TimeoutError)
    assert str(err.last_error) == "超时"
    assert isinstance(err.__cause__, TimeoutError)
    assert str(err.__cause__) == "超时"
    assert sleep_mock.call_count == 0


@pytest.mark.parametrize(
    ("max_attempts", "delay_seconds", "retryable_exceptions", "exception", "match"),
    [
        (
            -1,
            0,
            (TimeoutError, ConnectionError),
            ValueError,
            "max_attempts 必须是大于等于 1 的整数，布尔值不视为合法整数",
        ),
        (
            1.5,
            0,
            (TimeoutError, ConnectionError),
            ValueError,
            "max_attempts 必须是大于等于 1 的整数，布尔值不视为合法整数",
        ),
        (
            True,
            0,
            (TimeoutError, ConnectionError),
            ValueError,
            "max_attempts 必须是大于等于 1 的整数，布尔值不视为合法整数",
        ),
        (
            5,
            -1,
            (TimeoutError, ConnectionError),
            ValueError,
            "delay_seconds 必须是大于等于 0 的整数或浮点数，布尔值不合法",
        ),
        (
            5,
            True,
            (TimeoutError, ConnectionError),
            ValueError,
            "delay_seconds 必须是大于等于 0 的整数或浮点数，布尔值不合法",
        ),
        (
            5,
            0,
            (),
            ValueError,
            "retryable_exceptions 为非空元组",
        ),
        (
            5,
            0,
            [TimeoutError, ConnectionError],
            ValueError,
            "retryable_exceptions 为非空元组",
        ),
        (
            5,
            0,
            (TimeoutError, ConnectionError, 123),
            ValueError,
            "retryable_exceptions 的每个元素都必须是 Exception 的异常类",
        ),
    ],
)
def test_retry_policy(
    max_attempts: int,
    delay_seconds: int,
    retryable_exceptions: tuple[type[Exception], ...],
    exception: type[Exception],
    match: str,
) -> None:
    with pytest.raises(exception, match=match):
        RetryPolicy(max_attempts, delay_seconds, retryable_exceptions)
