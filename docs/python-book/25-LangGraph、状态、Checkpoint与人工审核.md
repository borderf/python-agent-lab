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

### 2.5 恢复前先过五道状态门

恢复输入不是“thread_id加一个approve”，而是当前任务快照、可信调用者、决定、当前时间和本次载荷摘要。依次检查租户、任务状态、权限有效期、载荷版本和外部效果状态；全部通过才允许进入恢复节点。

| 状态门 | 输入字段 | 通过条件 | 失败输出 |
| --- | --- | --- | --- |
| 身份 | caller_tenant、task.tenant_id | 完全相同且调用者已授权 | `wrong_tenant` |
| 生命周期 | status、expires_at | waiting_approval且未过期 | `task_not_resumable`或`approval_expired` |
| 载荷 | payload_hash、approved_hash | 相等且版本仍当前 | `stale_approval` |
| 决定 | decision | 仅approve/reject | `invalid_decision` |
| 效果 | status、effects、receipt | 未执行或可按原键核对 | `reconcile_required` |

下面把规则写成独立判定器。它不访问数据库，也不替代框架的interrupt/resume：

```python
def resume_gate(task, *, caller_tenant, decision, now, payload_hash):
    if caller_tenant != task["tenant_id"]:
        return {"allowed": False, "reason": "wrong_tenant"}
    if decision not in {"approve", "reject"}:
        return {"allowed": False, "reason": "invalid_decision"}
    if task["status"] != "waiting_approval":
        return {"allowed": False, "reason": "task_not_resumable"}
    if now >= task["expires_at"]:
        return {"allowed": False, "reason": "approval_expired"}
    if (payload_hash != task["approved_hash"]
            or task["payload_version"] != task["approved_version"]):
        return {"allowed": False, "reason": "stale_approval"}
    if decision == "reject":
        return {"allowed": True, "reason": "record_rejection"}
    if task["status"] == "executing" or task["effects"] > 0:
        return {"allowed": False, "reason": "reconcile_required"}
    return {"allowed": True, "reason": "resume_approved"}

base = {"tenant_id": "tenant-a", "status": "waiting_approval", "expires_at": "2026-10-02",
        "approved_hash": "h2", "payload_version": 2, "approved_version": 2, "effects": 0}
args = {"caller_tenant": "tenant-a", "decision": "approve", "now": "2026-10-01", "payload_hash": "h2"}
assert resume_gate(base, **args) == {"allowed": True, "reason": "resume_approved"}
assert resume_gate(base, **{**args, "caller_tenant": "tenant-b"})["reason"] == "wrong_tenant"
assert resume_gate(base, **{**args, "payload_hash": "h1"})["reason"] == "stale_approval"
assert resume_gate({**base, "approved_version": 1}, **args)["reason"] == "stale_approval"
assert resume_gate(base, **{**args, "now": "2026-10-02"})["reason"] == "approval_expired"
assert resume_gate(base, **{**args, "now": "2026-10-03"})["reason"] == "approval_expired"
assert resume_gate({**base, "status": "executing", "effects": 1}, **args)["reason"] == "task_not_resumable"
assert resume_gate(base, **{**args, "decision": "reject"}) == {"allowed": True, "reason": "record_rejection"}
print(resume_gate(base, **args))
```

预期输出为`{'allowed': True, 'reason': 'resume_approved'}`。只有原租户、未过期、载荷版本仍当前且哈希相同的批准进入`resume_approved`；到期时刻 `now == expires_at` 已经拒绝。拒绝只记录拒绝，不触发生效。`executing`会先在生命周期门被拒绝，生产对账器随后按原动作键查询，而不是重新走批准写入。这里的`effects`是判定输入，真实系统必须从可信账本读取，不能相信checkpoint里的副本。时间使用统一格式的ISO日期仅为教学简化，生产要处理时区。

**判定对错：** 错误租户、旧批准、过期、取消和执行中都不能重新产生效果，且每种拒绝有稳定原因，才算通过；能恢复报告但重复写入不通过。

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

下面是可运行示例，使用项目 `agent` 依赖组；`study-example: S25C` 会由 `verify_textbook.py` 实际执行。SQLite 文件只放在临时目录，`prepare` 子进程退出后，再由 `resume` 子进程打开同一数据库。三个线程模拟 P200 的批准、拒绝和旧版本三次独立运行。

```python
# study-example: S25C
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

WORKER = r'''
import json
import sys
from typing import TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

class Approval(TypedDict):
    decision: str
    version: int

class State(TypedDict, total=False):
    tenant: str
    task: str
    version: int
    decision: str
    status: str
    effects: int

def review(state: State):
    answer = interrupt(
        {"task_id": state["task"], "version": state["version"]},
        response_schema=Approval,
    )
    if type(answer["version"]) is not int or answer["version"] != state["version"]:
        raise ValueError("stale approval")
    if answer["decision"] not in {"approve", "reject"}:
        raise ValueError("invalid decision")
    approved = answer["decision"] == "approve"
    return {"decision": answer["decision"],
            "status": "completed" if approved else "rejected",
            "effects": state["effects"] + int(approved)}

def config(task: str):
    return {"configurable": {"thread_id": f"tenant-a:{task}"}}

def resume(graph, task: str, decision: str, version: int):
    cfg = config(task)
    snapshot = graph.get_state(cfg)
    if not snapshot.next:                 # 已完成：返回原结果，不再次进入节点
        return dict(snapshot.values)
    if version != snapshot.values["version"]:
        return "stale_approval"            # 不把错误值交给图消费
    graph.invoke(Command(resume={"decision": decision, "version": version}), cfg)
    return dict(graph.get_state(cfg).values)

mode, database = sys.argv[1:3]
with SqliteSaver.from_conn_string(database) as saver:
    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    graph = builder.compile(checkpointer=saver)
    cases = {"P200-approve": ("approve", 2),
             "P200-reject": ("reject", 2),
             "P200-stale": ("approve", 1)}
    output = {}
    if mode == "prepare":
        for task in cases:
            cfg = config(task)
            graph.invoke({"tenant": "tenant-a", "task": task, "version": 2,
                          "effects": 0}, cfg)
            snapshot = graph.get_state(cfg)
            output[task] = {"values": dict(snapshot.values),
                            "interrupts": [item.value for item in snapshot.interrupts]}
    else:
        for task, (decision, version) in cases.items():
            output[task] = resume(graph, task, decision, version)
        assert graph.get_state(config("P200-stale")).interrupts
        output["duplicate"] = resume(graph, "P200-approve", "reject", 2)
    print(json.dumps(output, ensure_ascii=False))
'''

with TemporaryDirectory(prefix="s25c-") as directory:
    database = str(Path(directory) / "checkpoints.sqlite")

    def run(mode):
        return json.loads(subprocess.check_output(
            [sys.executable, "-X", "utf8", "-c", WORKER, mode, database],
            text=True, encoding="utf-8"))

    prepared = run("prepare")              # 此进程结束后才执行下一行
    resumed = run("resume")

assert all(item["interrupts"] == [{"task_id": task, "version": 2}]
           for task, item in prepared.items())
assert all(item["values"]["effects"] == 0 for item in prepared.values())
assert resumed["P200-approve"]["status"] == "completed"
assert resumed["P200-approve"]["effects"] == 1
assert resumed["P200-reject"]["status"] == "rejected"
assert resumed["P200-reject"]["effects"] == 0
assert resumed["P200-stale"] == "stale_approval"
assert resumed["duplicate"]["decision"] == "approve"
assert resumed["duplicate"]["effects"] == 1
print(json.dumps(resumed, ensure_ascii=False))
```

真实采购任务还要保存报告、`payload_version`、`payload_hash`、缺件与预算；本例用版本号演示旧批准边界。暂停时三个线程的 `effects` 都为0，恢复后批准路径为1、拒绝路径为0。

### 4.2 同一采购请求：重启、恢复与对账

按4.1的输出逐项核对：

1. `prepare` 在 `review` 的 `interrupt` 处暂停，`thread_id` 分别定位三个 P200 运行，SQLite 保存暂停状态。
2. `resume` 是新进程，重新编译图并用 `Command(resume=...)` 继续；批准进入 `completed`，拒绝进入 `rejected`。
3. `P200-stale` 用版本1恢复版本2，应用入口返回 `stale_approval`，没有消费中断，之后仍可提交正确版本。
4. 对已完成的 `P200-approve` 再提交一次“拒绝”，入口因 `snapshot.next` 为空而返回原批准结果，`effects` 仍为1。

`thread_id` 只是定位键，例中的 `tenant-a` 是可信夹具，不是认证实现。节点重新执行时会再次检查决定和版本。`effects` 仅是教学计数，生产必须以业务任务表、审批记录和动作账本为准：执行前冻结载荷，使用稳定 `(tenant_id, operation_type, action_id)` 动作键；远端已提交而本地缺回执时保持 `executing`，按原键查询或重试，不能改载荷或重复产生效果。

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

用自己的任务表、审批记录和动作键完成6步恢复契约：保存/读取→错租户与未批准拒绝→改载荷使批准失效→重放只有一次效果→回执丢失时冻结→新进程对账。最后把同一失败案例迁移到LangGraph（图版见4.1的S25C）：批准、拒绝、旧版本与重复resume四案在图版与DB版各跑一次，逐项对照effects计数（批准1、拒绝0、旧版本0、重复resume仍1）、拒绝原因（如`stale_approval`）与最终状态，保存`graph-vs-db.json`对照记录；丢回执一案由DB版契约验证，图版需另注入提交后失败再对照。迁移验收按[附录E W09](附录E-项目里程碑与交付检查.md#w09迁移到-langgraph)执行。该契约不覆盖审批人身份、批准过期、暂停期间撤权等完整授权规则，生产入口仍须独立验收。

**未通过时怎样定位：** checkpoint不是批准记录或效果账本；thread_id不是身份；executing时不能改载荷；pending不等于失败；错误resume被持久化后要按实际框架规则处理。

**带到下一步：** 第26章用同题比较固定流程、工具选择与恢复轨迹。

## 6. 验收与自测

**验收命令与产物：** 运行 `uv run --frozen python -m pytest tests/learner/contract_resume.py --learner-module learner_resume -q`，应6项通过；先运行2.5状态门探针，确认错租户、旧批准、过期和执行中均被拒绝。交付暂停、杀进程、重启、恢复和效果计数的记录，并包含错误租户、旧批准与重复resume。该命令只验证DB版任务状态机（第16章风格），不覆盖图版迁移；图版另运行4.1的S25C，并按第5节口径与DB版对照effects与拒绝原因，记入W09。

**判定对错：** 状态可恢复且外部效果仍为1才算通过；只读回报告、绕过当前权限或重复resume产生新效果，均不通过。

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
