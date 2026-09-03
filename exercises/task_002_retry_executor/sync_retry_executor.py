import time
from dataclasses import dataclass
import logging
import math
from typing import Callable, TypeVar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
T = TypeVar("T")


class RetryExhaustedError(Exception):
    def __init__(self, attempts, last_error):
        self.attempts: int = attempts
        self.last_error: Exception = last_error
        super().__init__(f"重试 {attempts} 次后仍然失败，最后一次异常为{type(last_error).__name__}: {last_error}")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay_seconds: float
    retryable_exceptions: tuple[type[Exception], ...] = (TimeoutError, ConnectionError)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or self.max_attempts < 1
        ):
            raise ValueError(
                "max_attempts 必须是大于等于 1 的整数，布尔值不视为合法整数"
            )
        if (
            not (
                isinstance(self.delay_seconds, int)
                or isinstance(self.delay_seconds, float)
            )
            or not math.isfinite(self.delay_seconds)
            or isinstance(self.delay_seconds, bool)
            or self.delay_seconds < 0
        ):
            raise ValueError(
                "delay_seconds 必须是大于等于 0 的整数或浮点数，布尔值不合法"
            )
        if (
            not isinstance(self.retryable_exceptions, tuple)
            or not self.retryable_exceptions
        ):
            raise ValueError("retryable_exceptions 为非空元组")
        for exc in self.retryable_exceptions:
            if not isinstance(exc, type) or not issubclass(exc, Exception):
                raise ValueError(
                    "retryable_exceptions 的每个元素都必须是 Exception 的异常类"
                )


def execute_with_retry(
    operation: Callable[[], T],
    policy: RetryPolicy,
    sleep_func: Callable[[float], None] = time.sleep,
) -> T:
    for i in range(1, policy.max_attempts + 1):
        try:
            result = operation()
            if i == 1:
                logger.info("首次尝试就成功")
            return result
        except Exception as e:
            if isinstance(e, policy.retryable_exceptions):
                if i < policy.max_attempts:
                    logger.warning(
                        f"当前尝试次数为 {i},最大尝试次数为 {policy.max_attempts},异常信息为{type(e).__name__}: {e}"
                    )
                    sleep_func(policy.delay_seconds)
                else:
                    logger.error(
                        f"当前已达到最大尝试次数 {policy.max_attempts},最后一次异常信息为{type(e).__name__}: {e}"
                    )
                    raise RetryExhaustedError(policy.max_attempts, e) from e
            else:
                raise
    raise RuntimeError("Unreachable: retry loop should always return or raise")
