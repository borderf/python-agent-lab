"""Implement in your own copy, then run tests/learner/contract_agent.py.

The tutorial in chapter 24 introduces these functions in dependency order:
registry -> validation -> execution -> loop -> trace -> budget.
"""


def tool_specs():
    raise NotImplementedError("步骤 1：只读工具的名称、参数与只读标记")


def execute_tool(name, arguments, *, tenant_id, repo):
    raise NotImplementedError("步骤 2–5：校验名称/参数/金额，注入租户，只返回白名单字段")


def parse_decision(raw):
    raise NotImplementedError("步骤 6–7：只接受 tool_call 与 final 两种精确结构")


def run(question, *, model, tenant_id, repo, max_steps=4):
    raise NotImplementedError("步骤 8–12：循环、call_id、trace、预算与最终回答")