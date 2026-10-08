"""
https://docs.python.org/zh-cn/3.14/tutorial/datastructures.html
Python中常见的数据结构：
- list: [1, 2, 3]
- tuple: ("1", 2, 3.00)
- set: {"1", "2", "3"}
- dict: {"name": "haha", "age": 18}
"""

orders = [
    {
        "id": "10001",
        "user": "Alice",
        "amount": 199.0,
        "status": "paid",
    },
    {
        "id": "10002",
        "user": "Bob",
        "amount": 399.0,
        "status": "pending",
    },
    {
        "id": "10003",
        "user": "Alice",
        "amount": 599.0,
        "status": "paid",
    },
    {
        "id": "10004",
        "user": "Tom",
        "amount": 99.0,
        "status": "cancelled",
    },
    {
        "id": "10004",
        "user": "Tom",
        "amount": 99.0,
        "status": "cancelled",
    },
]

# 查找已支付的订单
def get_paid_orders(orders):
    """
    查找已支付的订单
    """
    return [order for order in orders if order["status"] == "paid"]

# 计算销售总额
def calculate_total_amount(orders):
    """
    计算销售总额
    """
    return sum(order["amount"] for order in orders)

# 按客户分组
def group_orders_by_user(orders):
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
def sort_orders_by_amount(orders, reverse=False):
    """
    按金额排序订单
    """
    return sorted(orders, key=lambda order: order["amount"], reverse=reverse)

# 订单去重
def remove_duplicate_orders(orders):
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
def get_order_ids(orders):
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
