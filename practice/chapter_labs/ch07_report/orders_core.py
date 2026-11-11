"""Order report example for chapter 7: strict input, dedupe, totals."""

import json

FIELDS = {"id", "user", "amount_cents", "status"}
STATUSES = {"paid", "pending", "cancelled"}


def validate_order(row):
    """Return a normalized copy; reject anything outside the order contract."""
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError("订单字段必须恰好是 id/user/amount_cents/status")
    for field in ("id", "user"):
        value = row[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} 必须是非空文本")
    amount = row["amount_cents"]
    if type(amount) is not int or amount < 0:
        raise ValueError("amount_cents 必须是非负整数分")
    status = row["status"]
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError(f"非法订单状态: {status!r}")
    return {"id": row["id"].strip(), "user": row["user"].strip(),
            "amount_cents": amount, "status": status}


def load_orders(path):
    with open(path, encoding="utf-8") as stream:
        for line_number, text in enumerate(stream, 1):
            if not text.strip():
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第{line_number}行不是合法JSON") from exc
            try:
                yield validate_order(row)
            except ValueError as exc:
                raise ValueError(f"第{line_number}行: {exc}") from exc


def report(rows):
    by_id, conflicts = {}, []
    for row in rows:
        key = row["id"]
        if key not in by_id:
            by_id[key] = row
        elif by_id[key] != row:
            conflicts.append(key)
    if conflicts:
        raise ValueError("冲突:" + ",".join(sorted(set(conflicts))))
    paid = [row for row in by_id.values() if row["status"] == "paid"]
    return {"order_count": len(by_id),
            "paid_amount_cents": sum(row["amount_cents"] for row in paid)}