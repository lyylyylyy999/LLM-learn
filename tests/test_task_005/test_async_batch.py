import asyncio
from contextlib import suppress
from dataclasses import FrozenInstanceError
from typing import Any, cast
from unittest.mock import AsyncMock, call

import pytest

from exercises.task_005_async_batch.async_batch import ItemResult, async_map_limited


def test_single_item() -> None:
    worker = AsyncMock(side_effect=["3"])

    result = asyncio.run(
        async_map_limited(
            items=["3"],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [ItemResult(index=0, status="success", value="3", error=None)]
    assert worker.call_count == 1
    assert worker.call_args_list == [call("3")]
    assert worker.await_count == 1
    assert worker.await_args_list == [call("3")]


def test_tuple_items() -> None:
    worker = AsyncMock(side_effect=[1, 2])

    result = asyncio.run(
        async_map_limited(
            items=(1, 2),
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value=1, error=None),
        ItemResult(index=1, status="success", value=2, error=None),
    ]
    assert worker.call_count == 2
    assert worker.call_args_list == [
        call(1),
        call(2),
    ]
    assert worker.await_count == 2
    assert worker.await_args_list == [
        call(1),
        call(2),
    ]


def test_multiple_items() -> None:
    worker = AsyncMock(side_effect=[1, 2, 3])

    result = asyncio.run(
        async_map_limited(
            items=[1, 2, 3],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value=1, error=None),
        ItemResult(index=1, status="success", value=2, error=None),
        ItemResult(index=2, status="success", value=3, error=None),
    ]
    assert worker.call_count == 3
    assert worker.call_args_list == [
        call(1),
        call(2),
        call(3),
    ]
    assert worker.await_count == 3
    assert worker.await_args_list == [
        call(1),
        call(2),
        call(3),
    ]


def test_result_order() -> None:
    async def scenario() -> None:
        release_a = asyncio.Event()
        b_finished = asyncio.Event()

        completion_order: list[str] = []

        async def worker(item: str) -> str:
            if item == "A":
                await release_a.wait()

            if item == "B":
                completion_order.append(item)
                b_finished.set()
                return item

            completion_order.append(item)
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B"],
                worker=worker,
                max_concurrency=2,
            )
        )

        try:
            await asyncio.wait_for(
                b_finished.wait(),
                timeout=1.0,
            )

            assert completion_order == ["B"]

            release_a.set()

            result = await task

            assert completion_order == ["B", "A"]

            assert result == [
                ItemResult(index=0, status="success", value="A", error=None),
                ItemResult(index=1, status="success", value="B", error=None),
            ]

        finally:
            release_a.set()

            if not task.done():
                task.cancel()

            with suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_concurrency_limit() -> None:
    async def scenario() -> None:
        active = 0
        peak = 0

        two_active = asyncio.Event()
        release = asyncio.Event()

        async def worker(item: str) -> str:
            nonlocal active, peak

            active += 1
            peak = max(peak, active)

            if active == 2:
                two_active.set()

            await release.wait()

            active -= 1
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B", "C"],
                worker=worker,
                max_concurrency=2,
            )
        )

        try:
            await asyncio.wait_for(
                two_active.wait(),
                timeout=1.0,
            )

            assert active == 2
            assert peak == 2

            release.set()
            await task

            assert peak == 2

        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    asyncio.run(scenario())


def test_two_workers_wait_at_same_time() -> None:
    async def scenario() -> None:
        started_a = asyncio.Event()
        started_b = asyncio.Event()
        release = asyncio.Event()

        async def worker(item: str) -> str:
            if item == "A":
                started_a.set()
            elif item == "B":
                started_b.set()

            await release.wait()
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B"],
                worker=worker,
                max_concurrency=2,
            )
        )

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    started_a.wait(),
                    started_b.wait(),
                ),
                timeout=1.0,
            )

            assert not task.done()

        finally:
            release.set()

            if not task.done():
                task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_exist_exception() -> None:
    value_error = ValueError("value error")
    type_error = TypeError("type error")

    worker = AsyncMock(
        side_effect=[
            "123",
            value_error,
            "345",
            type_error,
        ]
    )

    result = asyncio.run(
        async_map_limited(
            items=["1", "2", "3", "4"],
            worker=worker,
            max_concurrency=2,
        )
    )

    assert result == [
        ItemResult(index=0, status="success", value="123", error=None),
        ItemResult(index=1, status="failure", value=None, error=value_error),
        ItemResult(index=2, status="success", value="345", error=None),
        ItemResult(index=3, status="failure", value=None, error=type_error),
    ]
    assert result[1].error is value_error
    assert result[3].error is type_error


def test_worker_return_None() -> None:
    async def worker(x: str) -> None:
        return None

    result = asyncio.run(
        async_map_limited(
            items=["1"],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [ItemResult(index=0, status="success", value=None, error=None)]


def test_empty_input() -> None:
    worker = AsyncMock(side_effect=["123"])

    result = asyncio.run(
        async_map_limited(
            items=[],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == []
    assert worker.call_count == 0


@pytest.mark.parametrize(
    ("max_concurrency", "exception", "match"),
    [
        (0, ValueError, "max_concurrency 必须是大于等于 1 的整数，布尔值不合法"),
        (-10, ValueError, "max_concurrency 必须是大于等于 1 的整数，布尔值不合法"),
        (2.3, ValueError, "max_concurrency 必须是大于等于 1 的整数，布尔值不合法"),
        (True, ValueError, "max_concurrency 必须是大于等于 1 的整数，布尔值不合法"),
    ],
)
def test_max_concurrency(
    max_concurrency: Any, exception: type[Exception], match: str
) -> None:
    worker = AsyncMock(return_value=["ok"])

    with pytest.raises(exception, match=match):
        asyncio.run(
            async_map_limited(
                items=[],
                worker=worker,
                max_concurrency=max_concurrency,
            )
        )
    assert worker.call_count == 0


def test_result_is_frozen() -> None:
    async def worker(x: str) -> str:
        return x

    result = asyncio.run(
        async_map_limited(
            items=["3"],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [ItemResult(index=0, status="success", value="3", error=None)]
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).index = 10


def test_max_concurrency_one() -> None:
    async def worker(x: int) -> int:
        return x

    result = asyncio.run(
        async_map_limited(
            items=[1, 2, 3],
            worker=worker,
            max_concurrency=1,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value=1, error=None),
        ItemResult(index=1, status="success", value=2, error=None),
        ItemResult(index=2, status="success", value=3, error=None),
    ]


def test_concurrency_greater_than_item_count() -> None:
    async def worker(x: int) -> int:
        return x

    result = asyncio.run(
        async_map_limited(
            items=[1, 2, 3],
            worker=worker,
            max_concurrency=10,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value=1, error=None),
        ItemResult(index=1, status="success", value=2, error=None),
        ItemResult(index=2, status="success", value=3, error=None),
    ]


def test_same_mutable_object_identity() -> None:
    shared = ["A"]

    async def worker(item: list[str]) -> list[str]:
        return item

    result = asyncio.run(
        async_map_limited(
            items=[shared, shared],
            worker=worker,
            max_concurrency=2,
        )
    )

    assert result[0].value is shared
    assert result[1].value is shared


def test_exception_object_can_be_success_value() -> None:
    exception_value = ValueError("this is a value")

    async def worker(item: str) -> Exception:
        return exception_value

    result = asyncio.run(
        async_map_limited(
            items=["A"],
            worker=worker,
            max_concurrency=1,
        )
    )

    assert result[0].status == "success"
    assert result[0].value is exception_value
    assert result[0].error is None


def test_external_cancellation_propagates() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def worker(item: str) -> str:
            started.set()
            await release.wait()
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A"],
                worker=worker,
                max_concurrency=1,
            )
        )

        await asyncio.wait_for(started.wait(), timeout=1.0)

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
