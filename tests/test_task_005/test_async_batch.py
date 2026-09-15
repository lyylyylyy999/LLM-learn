import asyncio
from dataclasses import FrozenInstanceError
import pytest
from unittest.mock import AsyncMock
from exercises.task_005_async_batch.async_batch import ItemResult, async_map_limited


def test_single_item() -> None:
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


def test_multiple_items() -> None:
    async def worker(x: int) -> int:
        return x

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


def test_result_order() -> None:
    async def scenario() -> None:
        release_a = asyncio.Event()
        b_finished = asyncio.Event()

        completion_order: list[str] = []

        async def worker(item: str) -> str:
            if item == "A":
                await release_a.wait()

            if item == "B":
                b_finished.set()

            completion_order.append(item)
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B"],
                worker=worker,
                max_concurrency=2,
            )
        )

        # 明确等待 B 已经执行到这里
        await b_finished.wait()

        assert completion_order == ["B"]

        # 再允许 A 完成
        release_a.set()

        result = await task

        assert completion_order == ["B", "A"]

        assert result == [
            ItemResult(index=0, status="success", value="A", error=None),
            ItemResult(index=1, status="success", value="B", error=None),
        ]

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

        async def worker(x: str) -> str:
            if x == "A":
                started_a.set()
            elif x == "B":
                started_b.set()

            await release.wait()
            return x

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B"],
                worker=worker,
                max_concurrency=2,
            )
        )

        await started_a.wait()
        await started_b.wait()

        assert not task.done()

        release.set()
        await task

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
    async def worker(x: int) -> int:
        return x

    result = asyncio.run(
        async_map_limited(
            items=[],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == []


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
    max_concurrency: int, exception: type[Exception], match: str
) -> None:
    worker = AsyncMock(side_effect=["123"])

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
        setattr(result[0], "index", 1)


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
