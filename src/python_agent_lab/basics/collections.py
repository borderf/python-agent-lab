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