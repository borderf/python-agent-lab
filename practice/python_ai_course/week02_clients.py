"""第 07、09、10 课；按章节添加 Pydantic 与 HTTPX 后实现。"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from .week01_orders import Order

if TYPE_CHECKING:
    import httpx


def validate_with_pydantic(raw: object) -> list[Order]:
    """07：定义 OrderModel，严格校验并 model_dump，行为与第一周校验一致。"""
    # TODO：学习 ConfigDict/Field；禁止额外字段，规范化字符串，拒绝 bool 金额。
    # 请在本模块顶层定义 OrderModel，供第三周复用；异常为 ValueError 或其子类。
    raise NotImplementedError("第 07 课：validate_with_pydantic")


def fetch_orders(client: "httpx.Client") -> list[Order]:
    """09：GET /orders → 检查 HTTP 状态 → 解析 JSON → 严格订单校验。"""
    # TODO：保留 HTTP/超时/JSON/校验错误，不将失败伪装为空列表。
    raise NotImplementedError("第 09 课：fetch_orders")


def parse_settings(environ: Mapping[str, str]) -> dict[str, float | int]:
    """10：返回 timeout_seconds(默认5.0)、max_concurrency(默认3)。"""
    # TODO：从 REQUEST_TIMEOUT/MAX_CONCURRENCY 读取；超时有限且>0，并发为正整数。
    # 不直接读全局 os.environ，便于测试传入独立字典。
    raise NotImplementedError("第 10 课：parse_settings")
