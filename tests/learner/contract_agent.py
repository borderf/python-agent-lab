"""Twelve progressive contracts for a read-only agent loop."""
import json
from copy import deepcopy

import pytest

ORDERS = [
    {"id": "A1", "tenant_id": "a", "user": "Alice", "amount_cents": 50000,
     "status": "paid", "access_token": "secret-A1", "internal_note": "do-not-leak"},
    {"id": "A2", "tenant_id": "a", "user": "Alice", "amount_cents": 29800, "status": "paid"},
    {"id": "A3", "tenant_id": "a", "user": "Bob", "amount_cents": 10000, "status": "pending"},
    {"id": "A4", "tenant_id": "a", "user": "Alice", "amount_cents": 1200, "status": "pending"},
    {"id": "A5", "tenant_id": "a", "user": "Alice", "amount_cents": 0, "status": "paid"},
    {"id": "B1", "tenant_id": "b", "user": "Alice", "amount_cents": 99900,
     "status": "paid", "access_token": "secret-B1"},
]

TOOL_CALL = {"type": "tool_call", "call_id": "C1", "name": "get_paid_total",
             "arguments": {"user": "Alice"}}
ORDER_CALL = {"type": "tool_call", "call_id": "C1", "name": "get_order",
              "arguments": {"order_id": "A1"}}
FINAL = {"type": "final", "content": "Alice 已支付 798 元"}


class Repo:
    def __init__(self, rows=None):
        self.rows = deepcopy(ORDERS if rows is None else rows)
        self.calls = 0

    def all(self):
        self.calls += 1
        return deepcopy(self.rows)


class Scripted:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.requests = []

    def __call__(self, messages):
        self.requests.append(deepcopy(messages))
        if not self.decisions:
            raise AssertionError("model called more times than scripted")
        return self.decisions.pop(0)


def call(implementation, name="get_paid_total", arguments=None, *, tenant_id="a", data=None):
    repo = Repo(data)
    return implementation.execute_tool(
        name, {"user": "Alice"} if arguments is None else arguments,
        tenant_id=tenant_id, repo=repo), repo


def test_s01_tool_specs_are_readonly_and_explicit(implementation):
    specs = implementation.tool_specs()
    assert set(specs) == {"get_paid_total", "get_order"}
    assert all(spec["readonly"] is True for spec in specs.values())
    assert specs["get_paid_total"]["parameters"] == ["user"]
    assert specs["get_order"]["parameters"] == ["order_id"]
    assert all("tenant" not in name for spec in specs.values() for name in spec["parameters"])


def test_s02_execute_returns_structured_data(implementation):
    result, repo = call(implementation)
    assert result == {"ok": True, "data": {"user": "Alice", "found": True,
                                           "paid_count": 3, "paid_amount_cents": 79800}}
    assert repo.calls == 1
    assert "secret-A1" not in json.dumps(result)
    empty, _ = call(implementation, data=[])
    assert empty == {"ok": True, "data": {"user": "Alice", "found": False,
                                          "paid_count": 0, "paid_amount_cents": 0}}
    for bad in (29.9, True, "29", -1):
        rows = [{"id": "X1", "tenant_id": "a", "user": "Alice",
                 "amount_cents": bad, "status": "paid"}]
        with pytest.raises(ValueError):
            implementation.execute_tool("get_paid_total", {"user": "Alice"},
                                        tenant_id="a", repo=Repo(rows))
    bad_status = [{"id": "X1", "tenant_id": "a", "user": "Alice",
                   "amount_cents": 1, "status": "paidd"}]
    with pytest.raises(ValueError):
        implementation.execute_tool("get_paid_total", {"user": "Alice"},
                                    tenant_id="a", repo=Repo(bad_status))
    with pytest.raises(ValueError):
        implementation.execute_tool("get_order", {"order_id": "X1"},
                                    tenant_id="a", repo=Repo(bad_status))
    bad_pending = [{"id": "X1", "tenant_id": "a", "user": "Alice",
                    "amount_cents": "29", "status": "pending"}]
    with pytest.raises(ValueError):
        implementation.execute_tool("get_paid_total", {"user": "Alice"},
                                    tenant_id="a", repo=Repo(bad_pending))
    with pytest.raises(ValueError):
        implementation.execute_tool("get_order", {"order_id": "X1"}, tenant_id="a",
                                    repo=Repo([{"id": "X1", "tenant_id": "a", "user": "Alice",
                                                "amount_cents": 29.9, "status": "paid"}]))
    result["data"]["paid_count"] = 99
    assert repo.rows[0]["amount_cents"] == 50000


def test_s03_unknown_tool_has_zero_business_calls(implementation):
    with pytest.raises(ValueError):
        implementation.execute_tool("delete_all", {}, tenant_id="a", repo=Repo())
    repo = Repo()
    with pytest.raises(ValueError):
        implementation.execute_tool("get_paid_total", {}, tenant_id="a", repo=repo)
    assert repo.calls == 0


def test_s04_arguments_must_match_exactly(implementation):
    for arguments in ({}, {"user": "Alice", "tenant_id": "b"}, {"user": " "}, {"user": 1}):
        repo = Repo()
        with pytest.raises(ValueError):
            implementation.execute_tool("get_paid_total", arguments, tenant_id="a", repo=repo)
        assert repo.calls == 0
    repo = Repo()
    with pytest.raises(ValueError):
        implementation.execute_tool("get_paid_total", {"user": "Alice"}, tenant_id=" ", repo=repo)
    assert repo.calls == 0


def test_s05_tenant_scope_is_injected_by_the_server(implementation):
    a, _ = call(implementation, tenant_id="a")
    b, _ = call(implementation, tenant_id="b")
    assert a["data"]["paid_amount_cents"] == 79800
    assert b["data"]["paid_amount_cents"] == 99900
    order, _ = call(implementation, name="get_order", arguments={"order_id": "A1"}, tenant_id="a")
    assert order == {"ok": True, "data": {"found": True, "order": {
        "id": "A1", "user": "Alice", "amount_cents": 50000, "status": "paid"}}}
    assert "secret-A1" not in json.dumps(order)
    missing, _ = call(implementation, name="get_order", arguments={"order_id": "B1"}, tenant_id="a")
    assert missing["data"] == {"found": False, "order": None}
    other, _ = call(implementation, name="get_order", arguments={"order_id": "B1"}, tenant_id="b")
    assert other["data"]["found"] is True
    assert "secret-B1" not in json.dumps(other)


def test_s06_parse_accepts_two_exact_shapes(implementation):
    tool = implementation.parse_decision(TOOL_CALL)
    assert tool == TOOL_CALL and tool is not TOOL_CALL
    final = implementation.parse_decision(FINAL)
    assert final == FINAL


def test_s07_parse_rejects_ambiguous_shapes(implementation):
    for raw in ({}, {"type": "tool_call", "call_id": "C1", "name": "get_paid_total"},
                {"type": "tool_call", "call_id": "C1", "name": "get_paid_total",
                 "arguments": {}, "extra": 1},
                {"type": "tool_call", "call_id": "", "name": "get_paid_total", "arguments": {}},
                {"type": "tool_call", "call_id": "C1", "name": "delete_all", "arguments": {}},
                {"type": "tool_call", "call_id": "C1", "name": "get_paid_total", "arguments": []},
                {"type": "final", "content": "ok", "extra": 1},
                {"type": "final", "content": " "},
                {"type": "text", "content": "ok"}):
        with pytest.raises(ValueError):
            implementation.parse_decision(raw)


def test_s08_run_executes_then_returns_final(implementation):
    model = Scripted([TOOL_CALL, FINAL])
    repo = Repo()
    result = implementation.run("Alice 付了多少", model=model, tenant_id="a", repo=repo)
    assert result["answer"] == FINAL["content"]
    assert result["steps"] == 2 and result["tool_calls"] == 1
    assert result["trace"][0]["call_id"] == "C1"
    assert result["trace"][0]["result"]["data"]["paid_amount_cents"] == 79800
    assert repo.calls == 1


def test_s09_loop_returns_the_observation_with_the_same_call_id(implementation):
    model = Scripted([ORDER_CALL, FINAL])
    repo = Repo()
    implementation.run("A1 的金额", model=model, tenant_id="a", repo=repo)
    second = model.requests[1]
    assert second[-1]["role"] == "tool" and second[-1]["call_id"] == "C1"
    assert second[-1]["content"]["data"]["order"] == {
        "id": "A1", "user": "Alice", "amount_cents": 50000, "status": "paid"}
    assert second[-2]["role"] == "assistant" and second[-2]["content"]["call_id"] == "C1"
    assert "tenant_id" not in json.dumps(second)
    assert "secret-A1" not in json.dumps(second)
    assert "access_token" not in json.dumps(second)
    assert "internal_note" not in json.dumps(second)


def test_s10_budget_and_call_id_are_enforced(implementation):
    model = Scripted([{**TOOL_CALL, "call_id": f"C{index}"} for index in range(1, 4)])
    repo = Repo()
    with pytest.raises(RuntimeError):
        implementation.run("Alice 付了多少", model=model, tenant_id="a", repo=repo, max_steps=2)
    assert repo.calls == 2
    duplicated = Scripted([TOOL_CALL, TOOL_CALL, FINAL])
    repo = Repo()
    with pytest.raises(ValueError):
        implementation.run("Alice 付了多少", model=duplicated, tenant_id="a", repo=repo)
    assert repo.calls == 1


def test_s11_bad_decision_stops_before_business_effect(implementation):
    bad = {"type": "tool_call", "call_id": "C1", "name": "get_paid_total",
           "arguments": {"user": "Alice", "tenant_id": "b"}}
    repo = Repo()
    before = deepcopy(repo.rows)
    with pytest.raises(ValueError):
        implementation.run("Alice 付了多少", model=Scripted([bad]), tenant_id="a", repo=repo)
    assert repo.calls == 0 and repo.rows == before


def test_s12_final_validation_and_empty_tool_path(implementation):
    repo = Repo()
    result = implementation.run("直接回答", model=Scripted([FINAL]), tenant_id="a", repo=repo)
    assert result["tool_calls"] == 0 and result["steps"] == 1 and repo.calls == 0
    for max_steps in (0, True, 11):
        with pytest.raises(ValueError):
            implementation.run("问题", model=Scripted([FINAL]), tenant_id="a", repo=repo,
                               max_steps=max_steps)
    with pytest.raises(ValueError):
        implementation.run("问题", model=Scripted([{"type": "final", "content": " "}]),
                           tenant_id="a", repo=repo)