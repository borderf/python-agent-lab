# 第23章　LangGraph、状态、Checkpoint 与人工审核

[上一章](22-agent-loop.md) · [全书目录](README.md) · [下一章](24-mcp.md)

## 1. 学习目标与前置知识

迁移图编排并处理暂停恢复。前置：第16、22章。

## 2. 基础知识讲解

State 描述任务共享的数据，Node 计算更新，Edge/条件边控制下一步。消息、证据、错误、业务状态各自有清楚字段；并发更新需要定义合并规则。

Checkpoint 保存执行状态，不等于业务动作记录；Store 解决其他持久数据用途。Interrupt 等待外部输入，resume 可能从相关节点开头重新执行，因此节点中的副作用必须考虑重放。

人工审批绑定身份、具体任务和载荷版本，载荷变化旧审批失效。图状态持久化、数据库事务和外部幂等应协调，而非用其中一个替代全部机制。

## 3. 原理讲解与推导

图把执行状态显式化，但不会替你解决权限、业务一致性与副作用。迁移前后使用同一数据、模型和工具比较行为。

### 项目化展开

#### 任务状态和恢复

```text
queued → running → waiting_approval → running → completed
             ↘ failed                 ↘ failed
waiting_approval → rejected
queued/running/waiting_approval → cancelled（按实际取消点记录）
```

失败重试记录新的 attempt；只在允许重试的错误上进行，保留历史。外部动作正在执行时，取消任务不能保证撤销业务效果，状态需对账而不能假定回滚。

区分四类数据：业务任务/状态转换、图 checkpoint、审批与动作记录、审计事件。Checkpoint 标识映射到当前用户有权访问的业务 task，不允许拿任意外部 thread_id 恢复他人任务。

#### 一个受保护的模拟写操作

只在 W10 加入 submit_review：把确认后的审查报告提交到模拟业务服务。不做真实下单、供应商封禁或真实资金操作。

- 审批绑定 task_id、action_type、payload_hash/版本、审批人、有效期。
- 原载荷或身份范围变化时，旧审批无效。
- 执行点再次检查权限和审批，使用 action_id/幂等键。
- 重放、重复 resume 和重试通过持久化动作账本确认结果；对外服务也需要幂等处理。
- 外部写入已完成但本地未记成功时，先查询/对账；不能简单重试造成双写。
- 拒绝和取消都保留事件；模型输出“用户已同意”不能代替审批记录。

### 图状态不是聊天记录的别名

State应说明字段含义和更新规则；消息可追加，证据可按ID合并，最终状态通常受约束覆盖。多个并行节点写同字段时，必须知道框架如何处理更新冲突，reducer是否满足所需合并语义。

恢复可能重新进入节点，因此把不可重复副作用隔离到受保护边界。持久化图状态、长期记忆、业务任务表和审计不是同一种数据，不应都塞进不断增长的消息列表。

## 4. 示例与逐步走查

### 不调用真实模型的最小图

以下需要按本章官方文档安装并锁定LangGraph；示例是状态更新，不包含持久化：

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
class State(TypedDict):
    total: int
def increment(state: State):
    return {"total": state["total"] + 1}
builder = StateGraph(State)
builder.add_node("increment", increment)
builder.add_edge(START, "increment")
builder.add_edge("increment", END)
graph = builder.compile()
assert graph.invoke({"total": 1})["total"] == 2
```

先解释输入、更新和结束，再增加条件边与工具；Checkpoint和Interrupt另加测试，不能从这个示例推断已具备恢复能力。

## 5. 动手练习

把手写循环改成图；加入审批中断、服务重启、重复resume；模拟写入成功后崩溃，对账并恢复。

## 6. 验收与自测

**行为验收：** 图与手写版规则一致；恢复身份不越权；批准前零写入；重复恢复不重复产生模拟效果。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

Graph state 与业务状态有什么差别？为什么重放节点不等于事务回滚？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.langchain.com/oss/python/langgraph/interrupts)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](22-agent-loop.md) · [下一章](24-mcp.md)
