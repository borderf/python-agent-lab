"""第 11–15 课：异步批量查询与 FastAPI 应用工厂。"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from .week01_orders import Order

if TYPE_CHECKING:
    from fastapi import FastAPI


async def collect_paid_totals(
    users: list[str],
    fetch_total: Callable[[str], Awaitable[int]],
    *,
    max_concurrency: int = 2,
    timeout_seconds: float = 1.0,
) -> dict[str, int]:
    """12：用户去重、限制并发、单项超时；失败时取消并等待所有剩余任务。"""
    # TODO：超时从获得并发名额开始；失败抛原始异常，不遗留后台任务。
    # 空输入返回 {}；非法 max_concurrency/timeout_seconds 抛 ValueError。
    raise NotImplementedError("第 12 课：collect_paid_totals")


def create_app(orders: list[Order]) -> "FastAPI":
    """13–14：提供 health、GET /reports、POST /reports，具体契约见第三周。"""
    # TODO：GET 可按 user 过滤，无此用户404；POST非法数据422，同ID冲突409。
    # POST不修改注入的数据；复用已完成的校验/报告函数。
    raise NotImplementedError("第 13–14 课：create_app")
