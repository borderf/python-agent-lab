"""第三周：异步检查无需网络；API 检查需要 FastAPI 和 HTTPX。"""

import asyncio
import json
from pathlib import Path

import pytest

from practice.python_ai_course import week03_service as work


def test_concurrency_and_user_dedup():
    async def scenario():
        active, peak = 0, 0
        seen = []
        async def fetch(user):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            seen.append(user)
            try:
                await asyncio.sleep(0)
                return {"Alice": 79800, "Bob": 0, "Tom": 0}[user]
            finally:
                active -= 1
        result = await work.collect_paid_totals(["Alice", "Bob", "Alice", "Tom"], fetch, max_concurrency=2)
        assert result == {"Alice": 79800, "Bob": 0, "Tom": 0}
        assert list(result) == ["Alice", "Bob", "Tom"]
        assert sorted(seen) == ["Alice", "Bob", "Tom"]
        assert 1 < peak <= 2
        assert active == 0
    asyncio.run(asyncio.wait_for(scenario(), timeout=2.0))


def test_timeout_cleans_up_tasks():
    async def scenario():
        active = set()
        async def fetch(user):
            active.add(user)
            try:
                await asyncio.Event().wait()
                return 0
            finally:
                active.remove(user)
        with pytest.raises(TimeoutError):
            await work.collect_paid_totals(["Alice", "Bob"], fetch, timeout_seconds=0.02)
        assert not active, "超时返回前，应等待所有任务清理"
    asyncio.run(asyncio.wait_for(scenario(), timeout=2.0))


def test_async_failure_cancels_other_tasks():
    async def scenario():
        active = set()
        ready = asyncio.Event()
        async def fetch(user):
            active.add(user)
            try:
                if user == "fail":
                    await ready.wait()
                    raise ValueError("upstream failure")
                ready.set()
                await asyncio.Event().wait()
                return 0
            finally:
                active.remove(user)
        with pytest.raises(ValueError, match="upstream failure"):
            await work.collect_paid_totals(["fail", "waiting"], fetch)
        assert not active
    asyncio.run(asyncio.wait_for(scenario(), timeout=2.0))


def test_async_empty():
    async def fetch(_):
        raise AssertionError("空输入不应调用回调")
    assert asyncio.run(asyncio.wait_for(work.collect_paid_totals([], fetch), timeout=2.0)) == {}


@pytest.mark.parametrize("kwargs", [{"max_concurrency": 0}, {"max_concurrency": True}, {"timeout_seconds": 0}, {"timeout_seconds": float("nan")}])
def test_async_invalid_options(kwargs):
    async def fetch(_):
        return 0
    with pytest.raises(ValueError):
        asyncio.run(asyncio.wait_for(work.collect_paid_totals([], fetch, **kwargs), timeout=2.0))


@pytest.fixture
def client():
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    rows = json.loads((Path(__file__).parent / "data" / "orders.json").read_text(encoding="utf-8"))
    with TestClient(work.create_app(rows)) as test_client:
        yield test_client


def test_api_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_reports(client):
    assert client.get("/reports").json()["paid_amount_cents"] == 79800
    alice = client.get("/reports", params={"user": "Alice"})
    assert alice.status_code == 200
    assert alice.json()["order_count"] == 2
    assert alice.json()["total_amount_cents"] == 79800
    assert client.get("/reports", params={"user": "Nobody"}).status_code == 404


def test_api_post_validation_and_conflict(client):
    row = {"id": "X", "user": "New", "amount_cents": 7, "status": "paid"}
    response = client.post("/reports", json={"orders": [row, row]})
    assert response.status_code == 200
    assert response.json()["input_count"] == 2
    assert response.json()["total_amount_cents"] == 7
    assert client.post("/reports", json={"orders": [dict(row, amount_cents=True)]}).status_code == 422
    assert client.post("/reports", json={"orders": [row, dict(row, amount_cents=8)]}).status_code == 409
    assert client.get("/reports").json()["order_count"] == 4
