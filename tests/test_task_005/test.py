import asyncio


async def worker(name: str, delay: float) -> str:
    print(f"{name} start")

    await asyncio.sleep(delay)

    print(f"{name} finish")
    return f"{name} result"


async def main() -> None:
    results = await asyncio.gather(
        worker("A", 3),
        worker("B", 1),
        worker("C", 2),
    )

    print("results:", results)


asyncio.run(main())
