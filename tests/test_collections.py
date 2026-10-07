from python_agent_lab.basics.collections import (
    get_paid_orders,
)


def test_get_paid_orders():
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
    ]

    paid_orders = get_paid_orders(orders)
    assert len(paid_orders) == 2
    assert all(order["status"] == "paid" for order in paid_orders)