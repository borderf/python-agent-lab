"""
https://docs.python.org/zh-cn/3.14/tutorial/datastructures.html
Python中常见的数据结构：
- list: [1, 2, 3]
- tuple: ("1", 2, 3.00)
- set: {"1", "2", "3"}
- dict: {"name": "haha", "age": 18}
"""

from typing import Literal, TypedDict

OrderStatus = Literal["paid", "pending", "cancelled"]

"""
TypedDict 的作用主要是告诉 IDE、Pyright、mypy 这类静态类型检查工具：
“这个 dict 应该有哪些 key，每个 key 的 value 应该是什么类型。”
它不会在运行时自动验证 JSON。
如果你需要：
从 JSON / HTTP / LLM Tool Call 中拿到数据后，在运行时真的验证它

那就更适合用 Pydantic。
"""


"""
为什么无法精确表示小数 0.1
十进制小数转换为二进制表示的方法：乘2取整，依此排列，直到小数部分为0
比如 0.1 * 2 = 0.2 -> 0
.2 * 2 = 0.4 -> 0
.4 * 2 = 0.8 -> 0
.8 * 2 = 1.6 -> 1
.6 * 2 = 1.2 -> 1
.2 * 2 = 0.4 -> 0
.4 * 2 = 0.8 -> 0
.8 * 2 = 1.6 -> 1
.6 * 2 = 1.2 -> 1
.2 * 2 = 0.4 -> 0
.4 * 2 = 0.8 -> 0
.8 * 2 = 1.6 -> 1
.6 * 2 = 1.2 -> 1
.2 * 2 = 0.4 -> 0
...
所以 0.1 的二进制表示是 0.000110011001100...

所以 0.1 在二进制中无法精确表示，导致在计算机中存储时会有微小的误差。
进行计算的时候，这些微小的误差会累积，最终导致结果不准确。
如果你需要精确表示小数，建议使用 decimal.Decimal 类型。

decimal.Decimal 是 Python 标准库中的一个类，用于进行高精度的十进制浮点数运算。它可以避免二进制浮点数表示带来的精度问题，适合用于财务计算等需要高精度的场景。
使用 decimal.Decimal 时，需要注意以下几点：
1. 导入 decimal 模块：
2. 创建 Decimal 对象时，最好使用字符串而不是浮点数，以避免浮点数的精度问题。例如：
from decimal import Decimal
a = Decimal("0.1")
3. Decimal 对象之间的运算会保持高精度，但需要注意性能问题
4. Decimal 对象可以与整数和其他 Decimal 对象进行运算，但与浮点数运算时可能会引入精度问题，建议尽量避免。
"""
class Order(TypedDict):
    id: str
    user: str
    amount: float
    status: OrderStatus

orders = [
    Order(
        id="10001",
        user="Alice",
        amount=199.0,
        status="paid"
    ),
    Order(
        id="10002",
        user="Bob",
        amount=399.0,
        status="pending"
    ),
    Order(
        id="10003",
        user="Alice",
        amount=599.0,
        status="paid"
    ),
    Order(
        id="10004",
        user="Tom",
        amount=99.0,
        status="cancelled"
    ),
]


# 查找已支付的订单
# 给函数增加参数类型和返回值类型
def get_paid_orders(orders: list[Order]) -> list[Order]:
    """
    查找已支付的订单
    """
    return [order for order in orders if order["status"] == "paid"]

# 计算销售总额
"""
sum和生成器表达式的组合使用可以在不创建额外列表的情况下计算总和，从而节省内存。
原理：
1. 生成器表达式会在迭代时按需生成值，而不是一次性创建整个列表。
2. sum 函数会迭代生成器表达式，逐个累加值，从而计算总和。
优点：
- 节省内存：不需要创建额外的列表，尤其在处理大量数据时非常有用。
- 提高性能：生成器表达式在迭代时按需生成值，避免了不必要的计算和内存分配。
- 代码简洁：使用生成器表达式可以使代码更简洁易读。
- 灵活性：生成器表达式可以与其他函数组合使用，如 map、filter 等，从而实现更复杂的数据处理。
- 延迟计算：生成器表达式在需要时才会计算值，这对于处理大数据集或流式数据非常有用。
- 可组合性：生成器表达式可以与其他生成器表达式或迭代器组合使用，从而实现更复杂的数据处理流程。
- 可迭代性：生成器表达式返回的是一个迭代器，可以与其他迭代器一起使用，如 zip、enumerate 等，从而实现更复杂的数据处理流程。
缺点：
- 可读性：对于不熟悉生成器表达式的开发者，可能会觉得代码不够直观。
- 调试困难：生成器表达式在调试时可能不如列表推导式直观，因为它们不会一次性生成所有值。
- 一次性使用：生成器表达式只能迭代一次，如果需要多次使用结果，可能需要将其转换为列表或其他可迭代对象。
- 性能问题：在某些情况下，生成器表达式可能会比列表推导式稍慢，尤其是在需要多次迭代的情况下。
"""
def calculate_total_amount(orders: list[Order]) -> float:
    """
    计算销售总额
    """
    return sum(order["amount"] for order in orders)

# 按客户分组
def group_orders_by_user(orders: list[Order]) -> dict[str, list[Order]]:
    """
    按客户订单分组
    """
    group_orders = {}
    for order in orders:
        user = order["user"]
        if user not in group_orders:
            group_orders[user] = []
        group_orders[user].append(order)
    return group_orders

# 金额排序
def sort_orders_by_amount(orders: list[Order], reverse: bool = False) -> list[Order]:
    """
    按金额排序订单
    """
    return sorted(orders, key=lambda order: order["amount"], reverse=reverse)

# 订单去重
def remove_duplicate_orders(orders: list[Order]) -> list[Order]:
    """
    去掉重复订单
    """
    seen_ids = set()
    unique_orders = []
    for order in orders:
        if order["id"] not in seen_ids:
            unique_orders.append(order)
            seen_ids.add(order["id"])
    return unique_orders


# TODO(Day 1.2): 用集合表示订单 ID，并练习集合操作。
#   - 从 orders 得到所有唯一订单 ID、已支付订单 ID、非已支付订单 ID。
#   - 用差集求非已支付订单 ID；判断已支付 ID 是否为所有 ID 的子集。
#   - 比较原始订单 ID 列表长度与唯一 ID 集合长度，判断数据中是否有重复 ID。
#   验收：能说清 set 去重后不保留重复次数，也不应用它来依赖原始顺序。
# 获取订单ID、已支付ID、非已支付ID
def get_order_ids(orders: list[Order]) -> tuple[set[str], set[str], set[str]]:
    """
    获取订单ID、已支付ID、非已支付ID
    """

    order_ids = {order["id"] for order in orders}
    # 已支付ID
    paid_order_ids = {order["id"] for order in orders if order["status"] == "paid"}
    # 非已支付ID
    unpaid_order_ids = order_ids - paid_order_ids
    return (order_ids, paid_order_ids, unpaid_order_ids)


if __name__ == "__main__":
    paid_orders = get_paid_orders(orders)
    print("已支付的订单:")
    for order in paid_orders:
        print(order)
    print("-" * 20)
    total_amount = calculate_total_amount(orders)
    print(f"销售总额: {total_amount}")
    print("-" * 20)
    print("按客户分组的订单:")
    grouped_orders = group_orders_by_user(orders)
    for user, user_orders in grouped_orders.items():
        print(f"{user}: {user_orders}")
    print("-" * 20)
    print("按金额排序的订单:")
    sorted_orders = sort_orders_by_amount(orders, True)
    for order in sorted_orders:
        print(order)

    print("-" * 20)
    print("去重后的订单:")
    unique_orders = remove_duplicate_orders(orders)
    for order in unique_orders:
        print(order)

    print("获取订单各种ID")
    order_id_tuple = get_order_ids(orders)
    print(f"订单ID、已支付订单ID、未支付订单ID：{order_id_tuple}")
