import time
from functools import wraps
from typing import Callable, TypeVar, ParamSpec
from exercises.task_002_retry_executor.sync_retry_executor import (
    execute_with_retry,
    RetryPolicy,
)


R = TypeVar("R")
P = ParamSpec("P")


def retry(
    policy: RetryPolicy,
    sleep_func: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            def operation() -> R:
                return func(*args, **kwargs)

            return execute_with_retry(operation, policy, sleep_func)

        return wrapper

    return decorator
