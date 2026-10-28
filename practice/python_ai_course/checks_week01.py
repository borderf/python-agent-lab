"""显式运行此文件；初始 TODO 尚未实现时，失败是正常的学习反馈。"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from practice.python_ai_course import week01_orders as work

DATA = Path(__file__).parent / "data"


@pytest.fixture
def orders():
    return json.loads((DATA / "orders.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("value,expected", [(" Alice ", "Alice"), ("alice", "alice")])
def test_name_normalization(value, expected):
    assert work.normalize_name(value) == expected


@pytest.mark.parametrize("value", ["", " \t ", None, 123])
def test_name_invalid(value):
    with pytest.raises(ValueError):
        work.normalize_name(value)


@pytest.mark.parametrize("value,expected", [(0, "0.00"), (1, "0.01"), (1999, "19.99"), (2000, "20.00")])
def test_money_format(value, expected):
    assert work.format_cents(value) == expected


@pytest.mark.parametrize("value", [-1, True, 19.99, "1999"])
def test_money_format_invalid(value):
    with pytest.raises(ValueError):
        work.format_cents(value)


def test_paid_filter(orders):
    assert [row["id"] for row in work.get_paid_orders(orders)] == ["10001", "10003"]
    assert work.get_paid_orders([]) == []


def test_ids(orders):
    assert work.collect_ids(orders) == (
        {"10001", "10002", "10003", "10004"}, {"10001", "10003"}, {"10002", "10004"},
    )
    assert work.collect_ids([]) == (set(), set(), set())


@pytest.mark.parametrize("status,expected", [(None, 129600), ("paid", 79800), ("pending", 39900), ("cancelled", 9900)])
def test_money_total(orders, status, expected):
    result = work.total_amount_cents(orders, status)
    assert type(result) is int
    assert result == expected
    assert work.total_amount_cents([], status) == 0


def test_money_not_hardcoded():
    rows = [
        {"id": "X", "user": "New", "amount_cents": 1999, "status": "paid"},
        {"id": "Y", "user": "New", "amount_cents": 1, "status": "paid"},
    ]
    assert work.total_amount_cents(rows) == 2000


def test_group(orders):
    groups = work.group_by_user(orders)
    assert {user: [row["id"] for row in rows] for user, rows in groups.items()} == {
        "Alice": ["10001", "10003"], "Bob": ["10002"], "Tom": ["10004"],
    }
    assert work.group_by_user([]) == {}


def test_duplicate(orders):
    rows = json.loads((DATA / "duplicate_orders.json").read_text(encoding="utf-8"))
    assert work.deduplicate_orders(rows) == orders
    assert work.deduplicate_orders([]) == []


@pytest.mark.parametrize("field,value", [("amount_cents", 99900), ("status", "cancelled"), ("user", "Other")])
def test_conflict(orders, field, value):
    duplicate = dict(orders[0], **{field: value})
    with pytest.raises(ValueError, match="10001"):
        work.deduplicate_orders([orders[0], duplicate])


@pytest.mark.parametrize("reverse,ids", [(False, ["C", "A", "B"]), (True, ["A", "B", "C"])])
def test_sort(reverse, ids):
    rows = json.loads((DATA / "tied_orders.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in work.sort_orders(rows, reverse)] == ids
    assert work.sort_orders([], reverse) == []


def test_input_unchanged(orders):
    before = deepcopy(orders)
    for fn in (work.get_paid_orders, work.group_by_user, work.sort_orders, work.deduplicate_orders):
        fn(orders)
        assert orders == before, f"{fn.__name__} 修改了输入"


def test_validation_normalizes_without_mutation(orders):
    orders[0]["user"] = " Alice "
    original = deepcopy(orders)
    result = work.validate_orders(orders)
    assert result[0]["user"] == "Alice"
    assert result is not orders and result[0] is not orders[0]
    assert orders == original
    assert work.validate_orders([]) == []


@pytest.mark.parametrize("bad_value", [True, "19900", 199.0, -1, None])
def test_validation_bad_money(orders, bad_value):
    orders[0]["amount_cents"] = bad_value
    with pytest.raises(ValueError):
        work.validate_orders(orders)


@pytest.mark.parametrize("raw", [{}, [123], [{}], None])
def test_validation_bad_shape(raw):
    with pytest.raises(ValueError):
        work.validate_orders(raw)


@pytest.mark.parametrize("change", [{"status": "refunded"}, {"id": " "}, {"extra": 1}])
def test_validation_bad_fields(orders, change):
    orders[0].update(change)
    with pytest.raises(ValueError):
        work.validate_orders(orders)


def test_load(orders, tmp_path):
    assert work.load_orders(DATA / "orders.json") == orders
    with pytest.raises(FileNotFoundError):
        work.load_orders(tmp_path / "missing.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        work.load_orders(invalid)


def test_report(orders):
    before = deepcopy(orders)
    expected = {
        "input_count": 4, "order_count": 4, "paid_count": 2,
        "total_amount_cents": 129600, "paid_amount_cents": 79800,
        "paid_amount_by_user": {"Alice": 79800, "Bob": 0, "Tom": 0},
    }
    assert work.build_report(orders) == expected
    duplicate_rows = json.loads((DATA / "duplicate_orders.json").read_text(encoding="utf-8"))
    assert work.build_report(duplicate_rows) == dict(expected, input_count=5)
    assert orders == before
    assert work.build_report([]) == {
        "input_count": 0, "order_count": 0, "paid_count": 0,
        "total_amount_cents": 0, "paid_amount_cents": 0, "paid_amount_by_user": {},
    }
