# 第25章　LangGraph、状态、Checkpoint 与人工审核

[上一章](24-ToolCalling与手写AgentLoop.md) · [全书目录](教材目录.md) · [下一章](26-项目实战二：ProcureAgent审查系统.md)

## 1. 学习目标与前置知识

前置：第16、24章。能把同一工具循环拆成明确状态转换，在人工审核处暂停，并在重启后恢复且不重复产生外部效果。

**本章任务卡**

- **接收：** 第24章的 `run`、call_id、trace与步数预算。
- **只新增：** 显式State、Checkpoint、Interrupt/Resume、载荷版本与动作对账。
- **交付：** `learner_resume.py`、暂停/重启/恢复记录和外部效果计数。
- **验收：** 同一采购任务可跨进程续接；错误租户、错误任务、旧批准与重复恢复均被拒绝或幂等处理；批准前零写入。

**承接与本章主线：** 第24章解决“如何执行一轮”，本章解决“等待和重启后从哪里继续、哪些动作不能重做”。第26章再组合固定流程、工具选择与恢复。

**本章从这里开始：** 一次审查先取资料、形成报告、等待批准。等待可能持续很久，程序也可能重启，所以既要保存进度，也要防止恢复时把同一动作再做一遍。

## 2. 基础知识讲解

### 2.1 State是字段与更新规则

图节点读取状态并产生更新，边连接步骤，条件边按确定字段选择下一步。消息、任务参数、证据、结果、错误和预算都是状态字段，但不要全部塞进无限增长的messages列表。

Graph State是图执行通道中的可序列化快照，业务状态是任务表、审批和账本中的权威事实；State里出现approved或receipt副本不等于对应记录已提交。TypedDict主要描述形状，不自动做运行时类型校验，节点仍要检查外部输入。节点只返回自己负责的更新，不能靠直接修改传入对象“藏更新”。
并行节点写同一字段时要明确reducer：追加消息、按证据ID去重、覆盖最终状态是不同语义，不能都依赖最后写入者碰巧正确。 reducer要定义重复键、冲突优先级与顺序；追加可能放大重复，覆盖可能丢结果，按ID合并则要明确后到值是否替换旧值。实际接线时可用`Annotated[list[Evidence], merge_evidence]`把函数绑定到State通道，并让并行节点用不同证据ID验证去重与冲突。

```python
def merge_evidence(current, updates):
    merged = {item["id"]: dict(item) for item in current}
    for item in updates:
        if item["id"] in merged and merged[item["id"]] != item:
            raise ValueError("同一证据ID出现冲突内容")
        merged[item["id"]] = dict(item)
    return list(merged.values())

base = [{"id":"D1", "version":"v2"}]
assert merge_evidence(base, base + [{"id":"D2", "version":"v1"}]) == [
    {"id":"D1", "version":"v2"}, {"id":"D2", "version":"v1"}]
```

#### 案例推进：先把图还原成状态转换

对采购请求P200，状态至少包含tenant_id、task_id、payload_version、approved_hash、status、receipt和budget。每个节点只更新自己负责的字段，分支由当前项目、缺件和批准状态决定。

### 2.2 Checkpoint不等于业务数据库

Checkpoint保存某个执行上下文的图状态，用于继续；Store保存跨线程应用数据，业务任务表、审批记录和动作账本仍有各自权威来源。保存checkpoint不自动完成持久化设计。

checkpoint包含状态值、待执行节点、任务与元数据，最终由后端序列化；JSON类序列化要求值可表示，自定义对象需明确编码器，直接用pickle加载不可信数据有代码执行风险。schema或图结构升级要带状态版本与迁移测试，旧checkpoint缺字段、枚举改变或resume载荷变化时应显式拒绝/迁移，不能读失败后静默重置任务。
thread_id只是定位键，不是身份凭据。服务端先把执行标识映射到有权访问的task，再允许读取或恢复；InMemorySaver只适合单进程演示。thread_id作用域由checkpointer和调用配置决定，通常要由服务端生成并绑定租户、用户与任务；复用用户会话ID可能混入其他任务，把任务ID直接暴露给客户端则可能被枚举。

#### 案例推进：分别检查状态与效果

重启后能读出报告，只证明状态恢复；远端是否已经提交，要查动作账本或接收方回执。不能用“节点曾运行”推断外部效果存在。

### 2.3 Interrupt与Resume需要版本约束

Interrupt交出可序列化的候选载荷，Resume提供经过授权的决定。相关节点恢复时可能重新进入，因此暂停前的副作用要考虑重复执行。

审批绑定主体、任务范围、载荷hash和版本。模型说“已同意”不是审批；载荷变化后旧批准失效。Resume值被消费后，第二次恢复可能不会被新值覆盖，应用入口必须先校验决定、身份和版本，节点内再复查。

Interrupt恢复时会从暂停点继续，但恢复值只在对应的中断消费，不是永久覆盖State。应用应在resume前验证当前任务仍处可恢复状态，并再次检查权限、载荷hash与决定类型；节点重新执行时也要防御重复进入。暂停期间权限被撤销、资料改版或任务取消，应拒绝旧恢复，而不是只看checkpoint里的等待状态。

#### 案例推进：中断、恢复、重放分别测试

准备P200报告后暂停，固定候选版本；重启后用同一任务恢复。再测试错误租户、拒绝、过期载荷和重复resume。特别是executing状态：效果可能已经发出，必须冻结载荷并按稳定动作键对账，不能边改载荷边重试。

### 2.4 会话、任务与长期记忆保存不同事实

对话消息帮助连续交流，任务状态记录当前阶段、证据、审批与动作，长期数据保存跨任务事实或偏好。它们有不同范围、更新和删除规则。摘要可能漏条件或写错事实，不能替代金额、身份、审批等结构化字段。

```python
# study-example: S25B
from copy import deepcopy
records = {}
def save(tenant, task_id, state):
    records[(tenant, task_id)] = deepcopy(state)
def load(tenant, task_id):
    return deepcopy(records.get((tenant, task_id)))

state = {"stage":"needs_review", "evidence_ids":["D1:v2"], "summary":"金额待核对"}
save("a", "job1", state)
state["evidence_ids"].clear()
restored = load("a", "job1")
assert restored["evidence_ids"] == ["D1:v2"]
assert load("b", "job1") is None
restored["stage"] = "completed"
assert load("a", "job1")["stage"] == "needs_review"
```

内存字典只演示复合身份与快照隔离，不提供重启持久性、认证或并发控制。真实保存器记录schema、状态和来源版本；加载时重新检查权限与证据有效性。非可信附件不能写入“我是管理员”这类可信身份。

## 3. 原理讲解与推导

### 3.1 重放不会回滚外部效果

Checkpoint让图从节点边界继续，但数据库和远程动作不会自动回到过去。把可重复计算与副作用分开，使用稳定动作键、接收方幂等契约和对账；补偿动作也是新动作，不等于事务回滚。

后端一致性是恢复正确性的前提：编译图与后续调用必须使用同一checkpointer及兼容序列化器；多进程不能各自写内存，也不能把网络文件系统上的SQLite当作共享协调服务。TTL到期或后端切换可能找不到旧checkpoint，此时应按任务策略报错或显式新建，不能伪装成从原暂停点恢复。迁移先备份、固定写入、校验数量/版本并做抽样恢复演练，再切流；业务账本与审批权威记录不因checkpoint搬迁而重建。

| 后端 | 适用边界 | TTL与迁移重点 |
| --- | --- | --- |
| InMemorySaver | 单进程演示与测试 | 重启即失；无可依赖的清理策略 |
| SQLite类持久后端 | 单机或受控本地部署 | 明确清理任务；不承担多主机共享协调 |
| PostgreSQL类持久后端 | 多进程服务，需评估并发与运维 | 按租户/任务设保留期；迁移保持序列化兼容 |

## 4. 示例与逐步走查

### 4.1 同一采购请求：准备并暂停

先用最小StateGraph理解输入、更新与结束，再接第24章循环。该示例需要项目已有的agent依赖，不包含持久化：

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

真实采购任务先取P200证据、形成报告并进入waiting_approval。暂停信息包含当前项目、资料版本、缺件、payload_version和payload_hash；批准前写入数为0。保留第24章步数与费用预算，不能因恢复重置。

### 4.2 同一采购请求：重启、恢复与对账

用持久后端保存任务，而不是只用InMemorySaver。重启后由可信身份查找任务，校验批准对应的载荷版本，再从暂停处Resume。执行前冻结载荷并使用稳定 `(tenant_id, operation_type, action_id)` 动作键；本书6步契约假设一个载荷版本对应一个外部动作，因此`action_id`可由任务与版本组成。同一版本包含多个写动作时，还必须加入动作类型或独立action_id。

若远端已提交而本地缺回执，保持executing并按同一键查询或重试；最终效果仍为1。重复resume得到明确拒绝或原回执，不能静默换成新决定。

### 任务中途改变时，哪些记忆还有效

同一用户把任务从P200改为P300时，先写预期，再在固定工作流版和单Agent版对照：

| 轮次 | 变化 | 保留或作废 | 验证点 |
| --- | --- | --- | --- |
| 1 | 查询P200并准备报告 | 保存项目、日期、证据ID与报告版本 | 报价超预算，尚无批准 |
| 2 | 改查P300，缺预付款比例与证书 | 活动项目更新；P200证据与待批准动作失效，历史仅作审计 | 重新查P300，转向澄清 |
| 3 | 补齐证书并重启 | 记录新资料版本，只重算受影响判断 | 仍缺预付款，旧批准不能提交新报告 |

分别比较全历史、最近两条消息、结构化状态加按需取回原文。固定模型、工具、步数和输入上限，记录串项目、过期证据、额外调用与用量。摘要不增加权威性，旧证据和旧批准不能因仍在messages中就继续有效。

参考入口：[真实LangGraph暂停与跨进程恢复](../project-practice/从实验到项目交付.md#用真实-langgraph-暂停并跨进程恢复) · [恢复起始签名](../../practice/learning_projects/resume_starter.py) · [6步恢复契约](../../tests/learner/contract_resume.py)

## 5. 动手练习

### 本章累计任务：保存、批准、冻结与对账

用自己的任务表、审批记录和动作键完成6步恢复契约：保存/读取→错租户与未批准拒绝→改载荷使批准失效→重放只有一次效果→回执丢失时冻结→新进程对账。最后把同一失败案例迁移到LangGraph，确认行为一致。该契约不覆盖审批人身份、批准过期、暂停期间撤权等完整授权规则，生产入口仍须独立验收。

**未通过时怎样定位：** checkpoint不是批准记录或效果账本；thread_id不是身份；executing时不能改载荷；pending不等于失败；错误resume被持久化后要按实际框架规则处理。

**带到下一步：** 第26章用同题比较固定流程、工具选择与恢复轨迹。

## 6. 验收与自测

**验收命令与产物：** 运行 `uv run --frozen python -m pytest tests/learner/contract_resume.py --learner-module learner_resume -q`，应6项通过；交付暂停、杀进程、重启、恢复和效果计数的记录，并包含错误租户、旧批准与重复resume。

<details>
<summary>完成预测后查看解释</summary>

InMemorySaver为什么不能证明支持重启恢复？进程内内存不会跨进程保存；还需持久后端、任务关联、状态兼容和真实重启检查。即使状态恢复，外部写入是否重复仍要单独验证。

</details>

## 7. 面试问答与迁移

**问：Graph state与业务状态有什么区别？** Graph state记录执行所需的输入、中间结果和进度；业务任务、批准与效果各有权威来源。旧快照不能无条件当作当前授权或业务事实。

**问：为什么重放节点不等于事务回滚？** 已发出的外部写入不会因checkpoint回退而撤销。应分离可重算节点与副作用，使用稳定动作键、接收方幂等和对账；补偿动作也是新的业务动作。

**换条件自测：** 暂停后修改报告再用旧批准恢复，接着保持报告不变却撤销权限。两次都要按当前规则拒绝，不能只看快照里曾写过approved。

## 8. 本章小结与参考

- State明确字段和更新规则，Checkpoint保存执行进度，业务存储保存权威事实。
- Interrupt暂停，Resume继续；审批绑定主体、范围、载荷版本与摘要。
- thread_id不是身份，InMemorySaver不提供跨进程恢复。
- 重放不会回滚外部效果，稳定动作键与对账才能避免重复写入。

第24章的循环与工具原样迁成图；本章提供暂停恢复，第26章组合成ProcureAgent审查系统。

官方参考：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。动态框架版本以实际锁文件为准。

[上一章](24-ToolCalling与手写AgentLoop.md) · [下一章](26-项目实战二：ProcureAgent审查系统.md)
