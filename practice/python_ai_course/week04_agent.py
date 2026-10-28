"""第 16–20 课：内部模型协议与只读订单工具；不绑定具体模型厂商。"""

from typing import Protocol

from .week01_orders import Order

Message = dict[str, object]
Decision = dict[str, object]


class Model(Protocol):
    def __call__(self, messages: list[Message]) -> Decision:
        """接收完整内部消息，返回尚待程序校验的决策。"""
        ...


def parse_decision(payload: object) -> Decision:
    """17：严格区分 final/tool_call，拒绝额外字段、非法类型和空字符串。"""
    # TODO：协议见第四周；这里只检查结构，不检查具体工具是否在白名单。
    raise NotImplementedError("第 17 课：parse_decision")


def execute_tool(name: str, arguments: dict[str, object], orders: list[Order]) -> dict[str, object]:
    """18：只允许 get_paid_total(user) 与 get_order(order_id)，先去重再查询。"""
    # TODO：未知工具/参数不匹配/数据冲突抛ValueError；不存在记录按约定返回found=False。
    raise NotImplementedError("第 18 课：execute_tool")


def run_agent(
    question: str,
    orders: list[Order],
    model: Model,
    *,
    max_steps: int = 5,
) -> dict[str, object]:
    """19：调用、校验、执行、回传循环；返回answer/steps/tool_calls/trace。"""
    # TODO：max_steps计算每次模型调用，含最后final；超上限抛RuntimeError。
    # trace为工具消息列表；每条包含role='tool'/call_id/name/content。
    # 工具ValueError回传ok=False；非法模型决策直接报错；不修改输入。
    raise NotImplementedError("第 19 课：run_agent")
