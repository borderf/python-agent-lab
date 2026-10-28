"""第四周：假模型验证流程；真实模型表现需要另外评估。"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from practice.python_ai_course import week04_agent as work
from practice.python_ai_course.fake_model import ScriptedModel


@pytest.fixture
def orders():
    return json.loads((Path(__file__).parent / "data" / "orders.json").read_text(encoding="utf-8"))


def tool_call(name="get_paid_total", arguments=None):
    return {"type": "tool_call", "call_id": "call_1", "name": name, "arguments": {"user": "Alice"} if arguments is None else arguments}


@pytest.mark.parametrize("payload", [tool_call(), {"type": "final", "content": "你好"}])
def test_decision_valid(payload):
    original = deepcopy(payload)
    assert work.parse_decision(payload) == payload
    assert payload == original


@pytest.mark.parametrize("payload", [
    None, [], {"type": "execute_code", "content": "..."},
    {"type": "final", "content": " "}, {"type": "final", "content": "ok", "extra": 1},
    dict(tool_call(), arguments="{}"), dict(tool_call(), call_id=""),
])
def test_decision_invalid(payload):
    with pytest.raises(ValueError):
        work.parse_decision(payload)


@pytest.mark.parametrize("user,found,count,amount", [("Alice", True, 2, 79800), ("Bob", True, 0, 0), ("Nobody", False, 0, 0)])
def test_tool_paid_total(orders, user, found, count, amount):
    assert work.execute_tool("get_paid_total", {"user": user}, orders) == {
        "user": user, "found": found, "paid_count": count, "paid_amount_cents": amount,
    }


def test_tool_get_order(orders):
    assert work.execute_tool("get_order", {"order_id": "10002"}, orders) == {"found": True, "order": orders[1]}
    assert work.execute_tool("get_order", {"order_id": "99999"}, orders) == {"found": False, "order": None}


@pytest.mark.parametrize("name,args", [("unknown", {}), ("get_paid_total", {}), ("get_paid_total", {"user": ""}), ("get_paid_total", {"user": "Alice", "extra": 1})])
def test_tool_rejects_invalid(orders, name, args):
    with pytest.raises(ValueError):
        work.execute_tool(name, args, orders)


def test_tool_deduplicates_and_rejects_conflict(orders):
    original = deepcopy(orders)
    assert work.execute_tool("get_paid_total", {"user": "Alice"}, orders + [orders[0]])["paid_amount_cents"] == 79800
    with pytest.raises(ValueError):
        work.execute_tool("get_paid_total", {"user": "Alice"}, orders + [dict(orders[0], amount_cents=1)])
    assert orders == original


def test_agent_tool_result_is_returned_to_model(orders):
    model = ScriptedModel([tool_call(), {"type": "final", "content": "Alice 已支付 798.00 元。"}])
    original = deepcopy(orders)
    result = work.run_agent("Alice 已支付多少？", orders, model, max_steps=2)
    assert result["answer"] == "Alice 已支付 798.00 元。"
    assert result["steps"] == 2 and result["tool_calls"] == 1
    message = model.calls[1][-1]
    assert message["role"] == "tool" and message["call_id"] == "call_1"
    assert message["name"] == "get_paid_total"
    assert message["content"] == {"ok": True, "data": {"user": "Alice", "found": True, "paid_count": 2, "paid_amount_cents": 79800}}
    assert result["trace"] == [message]
    assert orders == original


def test_agent_tool_error_can_be_reported(orders):
    model = ScriptedModel([tool_call("unknown", {}), {"type": "final", "content": "不支持该工具"}])
    result = work.run_agent("测试未知工具", orders, model)
    content = model.calls[1][-1]["content"]
    assert content["ok"] is False and isinstance(content["error"], str)
    assert result["tool_calls"] == 1


def test_agent_budget(orders):
    model = ScriptedModel([tool_call(), tool_call(), tool_call()])
    with pytest.raises(RuntimeError):
        work.run_agent("持续查询", orders, model, max_steps=2)
    assert len(model.calls) == 2


def test_agent_invalid_decision(orders):
    with pytest.raises(ValueError):
        work.run_agent("测试坏响应", orders, ScriptedModel([{"type": "other"}]))


@pytest.mark.parametrize("value", [0, -1, True])
def test_agent_invalid_budget(orders, value):
    with pytest.raises(ValueError):
        work.run_agent("你好", orders, ScriptedModel([]), max_steps=value)


def test_agent_can_finish_without_tools(orders):
    result = work.run_agent("你好", orders, ScriptedModel([{"type": "final", "content": "你好"}]))
    assert result == {"answer": "你好", "steps": 1, "tool_calls": 0, "trace": []}
