"""可直接使用的离线模型替身，只按脚本返回，不执行网络请求。"""

from copy import deepcopy

from .week04_agent import Decision, Message


class ScriptedModel:
    def __init__(self, decisions: list[Decision]) -> None:
        self._decisions = deepcopy(decisions)
        self.calls: list[list[Message]] = []

    def __call__(self, messages: list[Message]) -> Decision:
        self.calls.append(deepcopy(messages))
        index = len(self.calls) - 1
        if index >= len(self._decisions):
            raise RuntimeError("假模型脚本已用完：请检查调用循环或增加决策")
        return deepcopy(self._decisions[index])
