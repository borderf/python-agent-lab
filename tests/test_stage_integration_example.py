"""Keep the first independent integration exercise aligned with its stated contract."""
from copy import deepcopy
from pathlib import Path
import re


def test_order_report_integration_contract():
    path = Path(__file__).resolve().parents[1] / "docs/project-practice/阶段整合任务.md"
    blocks = re.findall(r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    implementation = next(block for block in blocks if block.startswith("def report("))
    namespace = {}
    exec(compile(implementation, str(path), "exec"), namespace)
    report = namespace["report"]
    rows = [{"id": " A ", "amount_cents": 100}, {"id": "A", "amount_cents": 100}]
    original = deepcopy(rows)
    result = report(rows)
    assert result == {"ok": True, "error": None, "orders": [{"id": "A", "amount_cents": 100}]}
    assert rows == original
    assert result["orders"][0] is not rows[0]
    for invalid in (True, None, "100", -1):
        failed = report([rows[0], {"id": "B", "amount_cents": invalid}])
        assert failed == {"ok": False, "error": "invalid", "orders": []}
    conflict = report([rows[0], {"id": "A", "amount_cents": 101}])
    assert conflict["ok"] is False and conflict["error"] == "conflict" and conflict["orders"] == []
    assert report([]) == {"ok": True, "error": None, "orders": []}
