"""第二周：依赖未安装会跳过；跳过不代表练习已完成。"""

import json
from pathlib import Path

import pytest

from practice.python_ai_course import week02_clients as work

httpx = pytest.importorskip("httpx")
pytest.importorskip("pydantic")
DATA = Path(__file__).parent / "data"


@pytest.fixture
def orders():
    return json.loads((DATA / "orders.json").read_text(encoding="utf-8"))


def test_validation_valid(orders):
    assert work.validate_with_pydantic(orders) == orders
    assert work.validate_with_pydantic([]) == []


@pytest.mark.parametrize("value", ["19900", 199.0, True, -1])
def test_validation_strict(orders, value):
    orders[0]["amount_cents"] = value
    with pytest.raises(ValueError):
        work.validate_with_pydantic(orders)


def test_validation_name_and_extra(orders):
    orders[0]["user"] = " Alice "
    assert work.validate_with_pydantic(orders)[0]["user"] == "Alice"
    orders[0]["extra"] = 1
    with pytest.raises(ValueError):
        work.validate_with_pydantic(orders)


def test_http_success(orders):
    def handler(request):
        assert request.method == "GET" and request.url.path == "/orders"
        return httpx.Response(200, json=orders)
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
        assert work.fetch_orders(client) == orders


def test_http_status_error():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)), base_url="https://example.test") as client:
        with pytest.raises(httpx.HTTPStatusError):
            work.fetch_orders(client)


def test_http_timeout():
    def handler(request):
        raise httpx.ReadTimeout("模拟超时", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
        with pytest.raises(httpx.TimeoutException):
            work.fetch_orders(client)


@pytest.mark.parametrize("response", [httpx.Response(200, content=b"not-json"), httpx.Response(200, json={"orders": []})])
def test_http_invalid_payload(response):
    with httpx.Client(transport=httpx.MockTransport(lambda _: response), base_url="https://example.test") as client:
        with pytest.raises(ValueError):
            work.fetch_orders(client)


def test_settings():
    assert work.parse_settings({}) == {"timeout_seconds": 5.0, "max_concurrency": 3}
    assert work.parse_settings({"REQUEST_TIMEOUT": "2.5", "MAX_CONCURRENCY": "2"}) == {
        "timeout_seconds": 2.5, "max_concurrency": 2,
    }


@pytest.mark.parametrize("environment", [
    {"REQUEST_TIMEOUT": "0"}, {"REQUEST_TIMEOUT": "nan"}, {"REQUEST_TIMEOUT": "inf"},
    {"MAX_CONCURRENCY": "0"}, {"MAX_CONCURRENCY": "1.5"},
])
def test_settings_invalid(environment):
    with pytest.raises(ValueError):
        work.parse_settings(environment)
