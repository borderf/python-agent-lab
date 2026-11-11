"""Read-only agent loop: registry, validation, tenant scope, trace, budget.

The model proposes; this module validates, executes through a trusted repository,
returns only an allowlisted view, and stops on final or budget. Approval,
persistence and vendor SDK protocols are separate boundaries.
"""
from copy import deepcopy

TOOLS = {
    "get_paid_total": {"readonly": True, "parameters": ("user",)},
    "get_order": {"readonly": True, "parameters": ("order_id",)},
}
ORDER_FIELDS = ("id", "user", "amount_cents", "status")
ORDER_STATUSES = {"paid", "pending", "cancelled"}


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()


def _cents(value, order_id):
    if type(value) is not int or value < 0:
        raise ValueError(f"order {order_id} has invalid amount_cents")
    return value


def _order_view(row):
    missing = [field for field in ORDER_FIELDS if field not in row]
    if missing:
        raise ValueError("order missing required fields")
    order_id = _text(row["id"], "id")
    user = _text(row["user"], "user")
    status = row["status"]
    if not isinstance(status, str) or status not in ORDER_STATUSES:
        raise ValueError(f"order {order_id} has invalid status")
    return {"id": order_id, "user": user,
            "amount_cents": _cents(row["amount_cents"], order_id), "status": status}


def tool_specs():
    return {name: {"readonly": spec["readonly"], "parameters": list(spec["parameters"])}
            for name, spec in TOOLS.items()}


def _arguments(arguments, expected):
    if not isinstance(arguments, dict) or set(arguments) != set(expected):
        raise ValueError("arguments do not match the tool contract")
    return {name: _text(arguments[name], name) for name in expected}


def execute_tool(name, arguments, *, tenant_id, repo):
    tenant_id = _text(tenant_id, "tenant_id")
    if name not in TOOLS:
        raise ValueError("unknown tool")
    values = _arguments(arguments, TOOLS[name]["parameters"])
    rows = [deepcopy(row) for row in repo.all()]
    visible = [row for row in rows if row.get("tenant_id") == tenant_id]
    if name == "get_paid_total":
        matched = [row for row in visible if row.get("user") == values["user"]]
        paid = [_order_view(row) for row in matched if row.get("status") == "paid"]
        return {"ok": True, "data": {
            "user": values["user"], "found": bool(matched), "paid_count": len(paid),
            "paid_amount_cents": sum(row["amount_cents"] for row in paid)}}
    matched = [row for row in visible if row.get("id") == values["order_id"]]
    if not matched:
        return {"ok": True, "data": {"found": False, "order": None}}
    return {"ok": True, "data": {"found": True, "order": _order_view(matched[0])}}


def parse_decision(raw):
    if not isinstance(raw, dict):
        raise ValueError("decision must be an object")  # noqa: TRY004 - contract keeps one error type
    kind = raw.get("type")
    if kind == "tool_call":
        if set(raw) != {"type", "call_id", "name", "arguments"}:
            raise ValueError("unexpected tool_call fields")
        call_id = _text(raw["call_id"], "call_id")
        name = _text(raw["name"], "name")
        if name not in TOOLS:
            raise ValueError("unknown tool")
        if not isinstance(raw["arguments"], dict):
            raise ValueError("arguments must be an object")
        return {"type": "tool_call", "call_id": call_id, "name": name,
                "arguments": deepcopy(raw["arguments"])}
    if kind == "final":
        if set(raw) != {"type", "content"}:
            raise ValueError("unexpected final fields")
        return {"type": "final", "content": _text(raw["content"], "content")}
    raise ValueError("unknown decision type")


def run(question, *, model, tenant_id, repo, max_steps=4):
    question = _text(question, "question")
    tenant_id = _text(tenant_id, "tenant_id")
    if type(max_steps) is not int or not 1 <= max_steps <= 10:
        raise ValueError("max_steps must be an integer in 1..10")
    messages = [
        {"role": "system", "content": "Use read-only tools when needed. "
                                      "Answer with one final JSON object."},
        {"role": "user", "content": question},
    ]
    trace, seen = [], set()
    for step in range(1, max_steps + 1):
        decision = parse_decision(model(deepcopy(messages)))
        if decision["type"] == "final":
            return {"answer": decision["content"], "steps": step,
                    "tool_calls": len(trace), "trace": trace}
        call_id = decision["call_id"]
        if call_id in seen:
            raise ValueError("duplicate call_id")
        seen.add(call_id)
        result = execute_tool(decision["name"], decision["arguments"],
                              tenant_id=tenant_id, repo=repo)
        messages.append({"role": "assistant", "content": deepcopy(decision)})
        messages.append({"role": "tool", "call_id": call_id, "name": decision["name"],
                         "content": deepcopy(result)})
        trace.append({"step": step, "call_id": call_id, "name": decision["name"],
                      "arguments": deepcopy(decision["arguments"]), "result": deepcopy(result)})
    raise RuntimeError("step budget exhausted")