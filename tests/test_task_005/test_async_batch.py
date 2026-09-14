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
            items=["1", "2", "3"],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value="1", error=None),
        ItemResult(index=1, status="success", value="2", error=None),
        ItemResult(index=2, status="success", value="3", error=None),
    ]


def test_result_order() -> None:
    async def scenario() -> None:
        event_a = asyncio.Event()
        event_b = asyncio.Event()

        completion_order: list[str] = []

        async def worker(item: str) -> str:
            if item == "A":
                await event_a.wait()
            else:
                await event_b.wait()

            completion_order.append(item)
            return item

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B"],
                worker=worker,
                max_concurrency=2,
            )
        )

        event_b.set()
        await asyncio.sleep(0)

        event_a.set()

        result = await task

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

        async def worker(x: str) -> str:
            nonlocal active, peak

            active += 1
            peak = max(peak, active)

            if active == 2:
                two_active.set()

            await release.wait()

            active -= 1
            return x

        task = asyncio.create_task(
            async_map_limited(
                items=["A", "B", "C", "D"],
                worker=worker,
                max_concurrency=2,
            )
        )

        await two_active.wait()

        assert active == 2
        assert peak == 2

        release.set()
        await task

        assert peak == 2

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
    worker = AsyncMock(side_effect=["123", ValueError, "345", TypeError])
    result = asyncio.run(
        async_map_limited(
            items=["1", "2", "3", "4"],
            worker=worker,
            max_concurrency=2,
        )
    )
    assert result == [
        ItemResult(index=0, status="success", value="123", error=None),
        ItemResult(index=1, status="failure", value=None, error=ValueError),
        ItemResult(index=2, status="success", value="345", error=None),
        ItemResult(index=3, status="failure", value=None, error=TypeError),
    ]


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
    max_concurrency: object, exception: type[Exception], match: str
) -> None:
    async def worker(x: int) -> int:
        return x

    with pytest.raises(exception, match=match):
        result = asyncio.run(
            async_map_limited(
                items=[],
                worker=worker,
                max_concurrency=max_concurrency,
            )
        )


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
        result[0].index = 1
