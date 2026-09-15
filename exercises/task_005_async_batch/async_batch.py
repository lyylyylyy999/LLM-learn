import asyncio
from dataclasses import dataclass
from typing import Literal, TypeVar, Callable, Awaitable


R = TypeVar("R")
T = TypeVar("T")


@dataclass(frozen=True)
class ItemResult[R]:
    index: int
    status: Literal["success", "failure"]
    value: R | None
    error: Exception | None


async def async_map_limited(
    items: list[T],
    worker: Callable[[T], Awaitable[R]],
    max_concurrency: int,
) -> list[ItemResult[R]]:
    if (
        not isinstance(max_concurrency, int)
        or isinstance(max_concurrency, bool)
        or max_concurrency < 1
    ):
        raise ValueError("max_concurrency 必须是大于等于 1 的整数，布尔值不合法")
    if not isinstance(items, list):
        raise ValueError("items 必须是列表")
    if items == []:
        return []
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(index: int, item: T) -> ItemResult[R]:
        async with semaphore:
            try:
                value = await worker(item)
                return ItemResult(
                    index=index,
                    status="success",
                    value=value,
                    error=None,
                )
            except Exception as exc:
                return ItemResult(
                    index=index,
                    status="failure",
                    value=None,
                    error=exc,
                )

    return await asyncio.gather(
        *(run_one(index, item) for index, item in enumerate(items)),
    )
