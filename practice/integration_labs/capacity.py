"""Compare bounded-queue behavior under steady and burst fixture traffic."""
import asyncio
import json
from time import perf_counter


async def measure(interval: float, count: int = 20) -> dict:
    queue = asyncio.Queue(maxsize=4)
    records = []
    start = perf_counter()

    async def worker():
        while True:
            item = await queue.get()
            try:
                if item is None:
                    return
                request_id, arrived = item
                wait = perf_counter() - arrived
                await asyncio.sleep(0.04)
                records.append({"id": request_id, "status": "completed",
                                "arrival_ms": round((arrived - start) * 1000, 2), "queue_ms": round(wait * 1000, 2),
                                "elapsed_ms": round((perf_counter() - arrived) * 1000, 2)})
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as group:
        for _ in range(2):
            group.create_task(worker())
        for request_id in range(count):
            arrived = perf_counter()
            try:
                queue.put_nowait((request_id, arrived))
            except asyncio.QueueFull:
                records.append({"id": request_id, "status": "rejected",
                                "arrival_ms": round((arrived - start) * 1000, 2), "queue_ms": 0, "elapsed_ms": 0})
            await asyncio.sleep(interval)
        await queue.join()
        for _ in range(2):
            await queue.put(None)
    return {"arrival_interval_ms": interval * 1000, "total": count,
            "completed": sum(row["status"] == "completed" for row in records),
            "rejected": sum(row["status"] == "rejected" for row in records),
            "wall_ms": round((perf_counter() - start) * 1000, 2), "records": sorted(records, key=lambda row: row["id"])}


async def main():
    # sleep(0) yields without relying on platform-specific millisecond timers.
    for interval in (0.05, 0):
        print(json.dumps(await measure(interval), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
