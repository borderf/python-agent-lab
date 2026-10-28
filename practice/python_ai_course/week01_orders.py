"""第 01–05 课：在 TODO 处实现；业务规则见 docs/tutorial/README.md。"""

from pathlib import Path
from typing import Literal, TypedDict

OrderStatus = Literal["paid", "pending", "cancelled"]


class Order(TypedDict):
    id: str
    user: str
    amount_cents: int
    status: OrderStatus


class Report(TypedDict):
    input_count: int
    order_count: int
    paid_count: int
    total_amount_cents: int
    paid_amount_cents: int
    paid_amount_by_user: dict[str, int]


def normalize_name(value: str) -> str:
    """01：去两端空白，保留大小写；非字符串或结果为空时抛 ValueError。"""
    # TODO：先判断输入类型，再处理字符串；不要修改其他大小写。
    raise NotImplementedError("第 01 课：normalize_name")


def format_cents(cents: int) -> str:
    """01：非负整数分转两位小数字符串；拒绝 bool/float/负数。"""
    # TODO：用整数计算元与余下的分；结果不带货币单位。
    raise NotImplementedError("第 01 课：format_cents")


def get_paid_orders(orders: list[Order]) -> list[Order]:
    """02：返回已支付订单新列表，保持顺序，不修改输入。"""
    raise NotImplementedError("第 02 课：get_paid_orders")


def collect_ids(orders: list[Order]) -> tuple[set[str], set[str], set[str]]:
    """02：已去重输入 → 全部、已支付、非已支付 ID 三个集合。"""
    raise NotImplementedError("第 02 课：collect_ids")


def total_amount_cents(orders: list[Order], status: OrderStatus | None = None) -> int:
    """03：输入已去重；None 汇总全部，合法状态仅汇总该状态；空输入 0。"""
    raise NotImplementedError("第 03 课：total_amount_cents")


def group_by_user(orders: list[Order]) -> dict[str, list[Order]]:
    """03：按 user 分组，保持组内顺序；空输入返回 {}。"""
    raise NotImplementedError("第 03 课：group_by_user")


def deduplicate_orders(orders: list[Order]) -> list[Order]:
    """04：相同 ID 完全重复保留首条；字段冲突抛含该 ID 的 ValueError。"""
    # TODO：保留首见顺序；不要只记 ID 而丢失内容比较所需的信息。
    raise NotImplementedError("第 04 课：deduplicate_orders")


def sort_orders(orders: list[Order], reverse: bool = False) -> list[Order]:
    """04：按整数分稳定排序；返回新列表，不原地排序。"""
    raise NotImplementedError("第 04 课：sort_orders")


def validate_orders(raw: object) -> list[Order]:
    """05：严格校验顶层和字段；规范化 id/user；返回新的列表和字典。"""
    # TODO：详见教程入口统一规则；错误用 ValueError，提示记录位置/字段。
    # 类型标注 Order 不能替你检查运行时数据。
    raise NotImplementedError("第 05 课：validate_orders")


def load_orders(path: str | Path) -> list[Order]:
    """05：读 UTF-8 JSON 后校验；保留文件不存在和 JSON 语法错误异常。"""
    raise NotImplementedError("第 05 课：load_orders")


def build_report(orders: list[Order]) -> Report:
    """05：输入已校验；去重后汇总，input_count 保留原条数，空输入零统计。"""
    # TODO：含所有用户的已支付金额，未支付用户为 0；不修改输入。
    raise NotImplementedError("第 05 课：build_report")
