# 第24章　Tool Calling 与手写 Agent Loop

[上一章](23-项目实战一：DocPilot从零到检索系统.md) · [全书目录](教材目录.md) · [下一章](25-LangGraph、状态、Checkpoint与人工审核.md)

## 1. 学习目标与前置知识

前置：第12、18、20、23章。能把模型提出的工具请求交给程序校验并执行，把真实结果回传，再决定继续或停止。

**本章任务卡**

- **接收：** 第23章可追溯的证据链、权限边界与失败分类。
- **只新增：** 工具契约、决策解析、带call_id的手写循环、轨迹与步数预算。
- **交付：** `learner_agent.py`、两轮消息记录和12步契约结果。
- **验收：** 同一采购请求先提出工具、再由程序真实执行、最后依据tool消息回答；未知工具、坏参数和伪造租户在业务调用前失败。

**承接与本章主线：** 模型只提出动作，程序决定什么能发生。第25章再把同一循环变成可暂停、可恢复的任务。

**本章从这里开始：** 模型说“我要查询供应商”，查询真的发生了吗？Agent的核心不是多写几句提示，而是把意图、校验、执行、反馈与停止连成真实循环。

## 2. 基础知识讲解

### 2.1 工具请求还不是业务执行

先用普通函数直接调用一次，确认数据、单位和错误正确，再让模型选择。模型输出工具名和参数后，程序依次检查结构、允许名称、参数、可信身份与预算，最后才调用业务函数。工具说明帮助模型选择，实际授权属于程序和资源服务。

只读查询与写动作分开。租户、角色来自可信会话，不能由模型参数覆写；审批绑定具体载荷，查询成功也不等于获得写入授权。

schema描述字段形状，授权策略决定主体能否对具体资源做该动作，二者必须分开存储与检查。即使参数完全合法，仍可能因行级租户、资源实例、金额阈值或只读标记被拒绝；策略变更不应靠改工具描述生效。参数校验要在执行前覆盖必填/额外字段、类型、范围、枚举、长度和业务单位，bool不能冒充int；流式参数未完整闭合时不得提前调用。
工具描述中的“管理员”“无需审批”只是文本。应用按工具与动作默认拒绝，再显式授予最小资源范围；模型可见schema可以省略内部策略，但不能绕过它。

#### 案例推进：先固定采购请求的工具契约

同一请求是“为采购审查P200汇总Alice已支付金额”。工具 `get_paid_total` 只接受user，租户由服务端注入；返回整数分与允许字段。未知名称、额外tenant_id或空参数都必须在调用仓储前失败。

### 2.2 一轮循环必须回填真实观察

应用先请求模型，把返回解析为tool_call或final。工具请求通过校验后执行，结果带同一call_id追加为tool消息，再进入下一轮。没有回填，模型只能继续猜测；call_id用于请求与结果对应，但不是天然的业务幂等键。

多个工具结果可能乱序返回，应按call_id匹配，不能假设第一个结果属于第一个请求。

call_id只关联一轮请求与观察，重试或恢复时应另用稳定业务动作键表达“同一效果”，否则新call_id可能造成重复写入。结果匹配还要检查数量、未知ID与重复ID；已成功的部分不能因另一项失败被默认为全部成功。工具返回的字段同样不可信，必须按输出契约校验，不能把异常对象、提示文本或超时直接塞给模型当业务事实。

#### 案例推进：用乱序结果检查对应关系

```python
# study-example: S24C
def correlate(requests, results):
    wanted = [request["call_id"] for request in requests]
    received = [result["call_id"] for result in results]
    if len(set(wanted)) != len(wanted) or len(set(received)) != len(received):
        raise ValueError("调用标识重复")
    if set(wanted) != set(received):
        raise ValueError("结果缺失或出现未知调用")
    by_id = {result["call_id"]:result for result in results}
    return [by_id[call_id] for call_id in wanted]
requests = [{"call_id":"C1"}, {"call_id":"C2"}]
results = [{"call_id":"C2","value":20}, {"call_id":"C1","value":10}]
assert [r["value"] for r in correlate(requests, results)] == [10, 20]
try:
    correlate(requests, results[:1])
except ValueError:
    pass
else:
    raise AssertionError("缺失结果不能默认为成功")
```

### 2.3 循环需要多种预算

max_steps限制模型决策次数，单调用超时限制一次等待，总时限限制完整任务，token或费用限制资源，上下文预算限制消息体积。它们不能互相替代；必要约束放不下时应明确失败，不能静默删除后继续。

下面用字符数演示装箱，不是token计数，也不能用于计费。候选按相关性、来源和完整性排序，不能仅因短就优先。

观察截断要在工具出口先限行数、字段与字节数，保留结构化 `truncated`、总数和继续查询方式；不能截掉错误状态或金额单位，也不能让模型把“未显示”猜成0。为系统提示、问题、历史、工具结果分别预留预算，并给输出留空间；上下文压缩后的摘要不是权威观察，关键金额仍应回查原始工具。截断、超时和预算耗尽可能同时出现，应记录首个触发原因与未完成项。

```python
# study-example: S24B
def pack_context(required, candidates, budget):
    if type(budget) is not int or budget < 0:
        raise ValueError("budget必须为非负整数")
    used = sum(len(text) for text in required)
    if used > budget:
        raise ValueError("必要内容超出预算")
    selected = list(required)
    for text in candidates:
        if used + len(text) <= budget:
            selected.append(text)
            used += len(text)
    return selected
assert pack_context(["规则", "问题"], ["证据A", "很长的历史记录"], 7) == ["规则", "问题", "证据A"]
try:
    pack_context(["必要规则"], [], 1)
except ValueError:
    pass
else:
    raise AssertionError("不能丢掉必要规则后继续")
```

#### 案例推进：停止与完成证据同样重要

让替身永远请求工具，检查达到max_steps后停止并保留轨迹；再让它跳过工具直接猜金额。即使最终数字碰巧正确，也没有本次执行证据。

### 2.4 轨迹证明实际发生了什么

追踪保存每轮决策、实际调用、参数、结果和退出原因。金额回到确定性工具核对，不把不可验证的内部推理当执行凭证。固定流程适合步骤已知任务，Agent适合允许范围内需要动态选择的任务，应先用同一题比较。

部分失败时逐项记录成功、失败、未知与未执行；多写操作默认不是批事务，不能因一项失败就假设其他项已回滚。只读工具失败可澄清或降级，写动作超时属于效果未知，应停止自动重试、冻结载荷并按稳定键对账。达到步数、费用、时限、重复决策或高风险拒绝条件时明确停止；final只能陈述已证实结果，未完成项与动作回执必须单独保存。

```python
def summarize_actions(actions):
    summary = {state: 0 for state in ("succeeded", "failed", "unknown", "not_run")}
    for action in actions:
        if action["state"] not in summary:
            raise ValueError("unknown action state")
        summary[action["state"]] += 1
    summary["can_claim_complete"] = not any(action["state"] != "succeeded" for action in actions)
    return summary

actions = [{"state":"succeeded"}, {"state":"unknown"}, {"state":"not_run"}]
assert summarize_actions(actions) == {"succeeded":1, "failed":0, "unknown":1,
                                      "not_run":1, "can_claim_complete":False}
```

#### 案例推进：把P200的两次模型请求排成消息流

第一轮提出 `get_paid_total({"user":"Alice"})`；程序从可信会话取得租户并执行；第二轮收到带C1的真实结果后才允许final。trace中的steps与tool_calls分别计数，二者不能混用。

### 2.5 用事件序列判断循环是否真正闭环

把循环看成状态转换，比检查最终一句“已完成”更可靠。输入是带类型和call_id的事件；每处理一个事件就更新当前阶段；输出是停止原因、模型步数和已观察调用。未知事件、结果错配或必需工具未返回，都必须显式失败。

| 当前状态 | 事件 | 下一状态 | 输出/失败 |
| --- | --- | --- | --- |
| model_requested | tool_call C1 | waiting_tool | 记录C1与steps；参数授权此时已通过 |
| waiting_tool | tool_result C1 | model_requested | 记录真实观察；C2或重复结果失败 |
| model_requested | final | stopped | 必需调用均已观察才可结束 |
| 任意状态 | 超过max_steps或等待结束 | stopped/budget_exhausted | 保留未完成项，不伪造final |

下面只审计事件，不重复实现第24章的工具执行器：

```python
def audit_loop(events, required_calls, max_steps=4):
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps必须为正整数")
    stage, pending, observed, steps = "model_requested", None, [], 0
    for event in events:
        kind, call_id = event
        if kind == "tool_call":
            if stage != "model_requested" or not isinstance(call_id, str) or not call_id:
                return {"stop_reason": "invalid_tool_call", "steps": steps, "observed": observed}
            steps += 1
            if steps > max_steps:
                return {"stop_reason": "budget_exhausted", "steps": steps, "observed": observed}
            pending, stage = call_id, "waiting_tool"
        elif kind == "tool_result":
            if stage != "waiting_tool" or call_id != pending or call_id in observed:
                return {"stop_reason": "result_mismatch", "steps": steps, "observed": observed}
            observed.append(call_id)
            pending, stage = None, "model_requested"
        elif kind == "final":
            if stage != "model_requested":
                return {"stop_reason": "final_before_observation", "steps": steps, "observed": observed}
            steps += 1
            missing = [item for item in required_calls if item not in observed]
            if steps > max_steps:
                return {"stop_reason": "budget_exhausted", "steps": steps, "observed": observed}
            return {"stop_reason": "missing_observation" if missing else "final",
                    "steps": steps, "observed": observed}
        else:
            return {"stop_reason": "unknown_event", "steps": steps, "observed": observed}
    return {"stop_reason": "missing_tool_result" if stage == "waiting_tool" else "no_final",
            "steps": steps, "observed": observed}

closed = audit_loop([("tool_call", "C1"), ("tool_result", "C1"), ("final", None)], ["C1"])
assert closed == {"stop_reason": "final", "steps": 2, "observed": ["C1"]}
assert audit_loop([("final", None)], ["C1"])["stop_reason"] == "missing_observation"
assert audit_loop([("tool_call", "C1"), ("tool_result", "C2")], ["C1"])["stop_reason"] == "result_mismatch"
assert audit_loop([("tool_call", "C1")], ["C1"])["stop_reason"] == "missing_tool_result"
assert audit_loop([("tool_call", "C1"), ("tool_result", "C1"), ("final", None)], ["C1"], 1)["stop_reason"] == "budget_exhausted"
print(closed)
```

预期输出为`{'stop_reason': 'final', 'steps': 2, 'observed': ['C1']}`。关键断言说明：直接final会因缺少C1观察失败，C2不能冒充C1结果，只有tool_call而没有结果时仍处于等待。真实轨迹还要在执行前记录授权与参数校验；本探针只验证顺序契约，不能证明业务调用或金额正确。

**判定对错：** 同一call_id的请求与结果齐全、steps为2且停止原因为final才算闭环；最终文本正确但事件缺观察，或工具结果乱序匹配错，均不通过。

## 3. 原理讲解与推导

### 3.1 校验与回填把模型建议变成可验证动作

模型输出是外部输入。先验证并限制可执行范围，再把真实结果按调用标识回填，下一轮才有条件依据观察更新决策；跳过任何一步，最终文本都可能只是猜测。

## 4. 示例与逐步走查

### 4.1 同一采购请求：先提出，再执行

对“为采购审查P200汇总Alice已支付金额”，第一轮模型只提出请求：

```json
{"type":"tool_call","call_id":"C1","name":"get_paid_total","arguments":{"user":"Alice"}}
```

程序校验参数并从服务端取得tenant_id，真实计算后回传：

```json
{"role":"tool","call_id":"C1","name":"get_paid_total","content":{"ok":true,"data":{"paid_amount_cents":79800}}}
```

下一轮模型根据该结果组织回答。若把第一轮请求直接当成已执行，即使猜对79800，也不能证明系统完成查询。工具超时也不能伪装成金额0。

### 4.2 从零 12 步写出可验收的工具循环

新建 `learner_agent.py`，只使用标准库。下面的四段代码依次写入同一文件，后段调用前段函数；每完成一步，把 `--through-step` 推到当前步骤号。

```powershell
uv run --frozen python -m pytest tests/learner/contract_agent.py --learner-module learner_agent --through-step 1 -q
```

未到达步骤显示deselected，不是通过。[学习者验收与完整边界](../../tests/learner/练习说明.md#工具循环契约agent)

| 步骤 | 检查重点 |
| --- | --- |
| 1–5 | 工具名称、参数、只读标记、租户范围与字段白名单 |
| 6–7 | 只接受tool_call与final两种精确结构 |
| 8–9 | 真实执行、call_id回填、消息与trace |
| 10–12 | 步数预算、重复call_id、坏决策零执行与final校验 |

**步骤1–5，先固定执行边界。** 金额必须是整数分，bool、float、字符串和负数拒绝；状态必须在允许集合内。先验证本次查询涉及的全部记录，再筛选已支付，不能把paidd悄悄排除。工具返回给模型的订单视图只允许id、user、amount_cents、status，内部字段不得泄漏。

```python
from copy import deepcopy

TOOLS = {
    "get_paid_total": {"readonly": True, "parameters": ("user",)},
    "get_order": {"readonly": True, "parameters": ("order_id",)},
}
ORDER_FIELDS = ("id", "user", "amount_cents", "status")
ORDER_STATUSES = {"paid", "pending", "cancelled"}

def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()

def _cents(value, order_id):
    if type(value) is not int or value < 0:
        raise ValueError(f"order {order_id} has invalid amount_cents")
    return value

def _order_view(row):
    missing = [field for field in ORDER_FIELDS if field not in row]
    if missing:
        raise ValueError("order missing required fields")
    order_id = _text(row["id"], "id")
    user = _text(row["user"], "user")
    status = row["status"]
    if not isinstance(status, str) or status not in ORDER_STATUSES:
        raise ValueError(f"order {order_id} has invalid status")
    return {"id": order_id, "user": user,
            "amount_cents": _cents(row["amount_cents"], order_id), "status": status}

def tool_specs():
    return {name: {"readonly": spec["readonly"], "parameters": list(spec["parameters"])}
            for name, spec in TOOLS.items()}

def _arguments(arguments, expected):
    if not isinstance(arguments, dict) or set(arguments) != set(expected):
        raise ValueError("arguments do not match the tool contract")
    return {name: _text(arguments[name], name) for name in expected}

def execute_tool(name, arguments, *, tenant_id, repo):
    tenant_id = _text(tenant_id, "tenant_id")
    if name not in TOOLS:
        raise ValueError("unknown tool")
    values = _arguments(arguments, TOOLS[name]["parameters"])
    rows = [deepcopy(row) for row in repo.all()]
    visible = [row for row in rows if row.get("tenant_id") == tenant_id]
    if name == "get_paid_total":
        matched = [row for row in visible if row.get("user") == values["user"]]
        views = [_order_view(row) for row in matched]
        paid = [row for row in views if row["status"] == "paid"]
        return {"ok": True, "data": {
            "user": values["user"], "found": bool(matched), "paid_count": len(paid),
            "paid_amount_cents": sum(row["amount_cents"] for row in paid)}}
    matched = [row for row in visible if row.get("id") == values["order_id"]]
    if not matched:
        return {"ok": True, "data": {"found": False, "order": None}}
    return {"ok": True, "data": {"found": True, "order": _order_view(matched[0])}}
```

**步骤6–7，只接受两种决策形状。** tool_call必须恰好有type、call_id、name、arguments；final必须恰好有type、content。空ID、空content、未知工具或列表参数都在执行前拒绝。

```python
def parse_decision(raw):
    if not isinstance(raw, dict):
        raise ValueError("decision must be an object")
    kind = raw.get("type")
    if kind == "tool_call":
        if set(raw) != {"type", "call_id", "name", "arguments"}:
            raise ValueError("unexpected tool_call fields")
        call_id = _text(raw["call_id"], "call_id")
        name = _text(raw["name"], "name")
        if name not in TOOLS:
            raise ValueError("unknown tool")
        if not isinstance(raw["arguments"], dict):
            raise ValueError("arguments must be an object")
        return {"type": "tool_call", "call_id": call_id, "name": name,
                "arguments": deepcopy(raw["arguments"])}
    if kind == "final":
        if set(raw) != {"type", "content"}:
            raise ValueError("unexpected final fields")
        return {"type": "final", "content": _text(raw["content"], "content")}
    raise ValueError("unknown decision type")
```

**步骤8–9，把观察放回下一轮。** 每轮先复制决策给模型可见消息，执行后追加同一call_id的tool消息。steps是模型调用次数，tool_calls是成功取得工具观察的次数；trace保存成功调用的参数和结果。执行已发生但抛错或超时时，生产轨迹还要另记attempt、错误和未知效果，不能把本基线的成功计数当成全部动作证据。

```python
def run(question, *, model, tenant_id, repo, max_steps=4):
    question = _text(question, "question")
    tenant_id = _text(tenant_id, "tenant_id")
    if type(max_steps) is not int or not 1 <= max_steps <= 10:
        raise ValueError("max_steps must be an integer in 1..10")
    messages = [
        {"role": "system", "content": "Use read-only tools when needed. "
                                      "Answer with one final JSON object."},
        {"role": "user", "content": question},
    ]
    trace, seen = [], set()
    for step in range(1, max_steps + 1):
        decision = parse_decision(model(deepcopy(messages)))
        if decision["type"] == "final":
            return {"answer": decision["content"], "steps": step,
                    "tool_calls": len(trace), "trace": trace}
        call_id = decision["call_id"]
        if call_id in seen:
            raise ValueError("duplicate call_id")
        seen.add(call_id)
        result = execute_tool(decision["name"], decision["arguments"],
                              tenant_id=tenant_id, repo=repo)
        messages.append({"role": "assistant", "content": deepcopy(decision)})
        messages.append({"role": "tool", "call_id": call_id, "name": decision["name"],
                         "content": deepcopy(result)})
        trace.append({"step": step, "call_id": call_id, "name": decision["name"],
                      "arguments": deepcopy(decision["arguments"]), "result": deepcopy(result)})
    raise RuntimeError("step budget exhausted")
```

**步骤10–12，让失败也可验收。** 永远不final时按预算停止，重复call_id拒绝，坏决策零业务调用。下面的内存仓储与脚本模型把同一采购请求走成两步。

```python
class DemoRepo:
    def all(self):
        return [{"id": "A1", "tenant_id": "a", "user": "Alice",
                 "amount_cents": 79800, "status": "paid"}]

def demo_model(messages):
    if messages[-1]["role"] == "tool":
        return {"type": "final", "content": "Alice 已支付 798 元"}
    return {"type": "tool_call", "call_id": "C1", "name": "get_paid_total",
            "arguments": {"user": "Alice"}}

outcome = run("Alice 付了多少", model=demo_model, tenant_id="a", repo=DemoRepo())
assert outcome["answer"] == "Alice 已支付 798 元"
assert outcome["steps"] == 2 and outcome["tool_calls"] == 1
assert outcome["trace"][0]["call_id"] == "C1"
```

这12步不证明真实模型会选对工具，也不包含供应商原生协议、审批与跨进程恢复。接真实模型时由外层适配消息格式；审批与幂等接[学习者契约](../../tests/learner/练习说明.md#审批与幂等契约)，第25章再处理暂停恢复。

### 4.3 流式工具参数：增量装配，闭合才执行

第18章S18E处理半个UTF-8字符；这里把同一边界推进到工具参数。NDJSON每行本身是合法JSON，但`args_delta`只是参数字符串的一段：行可解析不等于参数完整。半段参数不执行，参数JSON闭合且流声明结束后才校验并执行。

```python
# study-example: S24D
import json

executed = []

def execute(name, arguments):
    if (name != "get_paid_total" or set(arguments) != {"user"}
            or not isinstance(arguments["user"], str) or not arguments["user"].strip()):
        raise ValueError("arguments do not match the tool contract")
    executed.append((name, dict(arguments)))
    return {"paid_amount_cents": 79800}

def consume(lines):
    buffer, name, ended = "", None, False
    for line in lines:
        event = json.loads(line)            # NDJSON行边界：每行自身合法
        if event.get("done") is True:
            ended = True
            break
        name = event.get("name", name)
        buffer += event["args_delta"]
        try:
            json.loads(buffer)
        except ValueError:
            continue                        # 半段参数：只累积，不执行
        # 即使此刻已闭合，也等结束事件，不提前执行
    if not ended:
        raise ValueError("stream missing end event")
    arguments = json.loads(buffer)          # 结束时仍半段：抛错，零执行
    return execute(name, arguments)

def delta(call_id, fragment, **extra):
    return json.dumps({"call_id": call_id, "args_delta": fragment, **extra}, ensure_ascii=False)

full = [delta("C1", '{"user":"Al', name="get_paid_total"),
        delta("C1", 'ice"}'),
        delta("C1", "", done=True)]
assert consume(full) == {"paid_amount_cents": 79800}
assert executed == [("get_paid_total", {"user": "Alice"})]
closed_early = [delta("C1", '{"user":"Alice"}', name="get_paid_total")]
for bad in (full[:2], [full[0], delta("C1", "", done=True)], closed_early):
    try:
        consume(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete or unended stream must not execute")
assert len(executed) == 1
print("executed", len(executed))
```

`S24D` 的预期结果是控制台输出 `executed 1`：完整流装配出 `{"user":"Alice"}` 并恰好执行一次；缺结束事件（`full[:2]`）、结束时仍半段参数（首段+done）与参数已闭合但流未结束（`closed_early`）都抛 `ValueError`，执行计数保持1。执行过程先按行解析事件、只累积 `args_delta`，结束事件后才整体解析参数并走工具契约校验。边界是：本探针不检查call_id错配与多调用交错（见S24C），也不处理UTF-8半字节（见第18章S18E）；真实供应商协议用自己的事件字段与完成原因，适配层仍须先确认流完整再执行。

## 5. 动手练习

### 本章累计任务：看见同一采购请求的真实工具执行

按4.2写自己的 `learner_agent.py`，逐步通过12步契约；保存P200请求的assistant调用、校验、执行、tool结果与final。分别注入未知工具、额外tenant_id和跳过工具的最终回答，核对执行次数。

**未通过时怎样定位：** 工具描述不授予权限；不完整流式参数不能提前执行；猜对结果不表示有本次工具证据；max_steps不替代超时和费用预算。

**带到下一步：** 第25章让同一循环等待审批并跨进程续接。

## 6. 验收与自测

**验收命令与产物：** 运行 `uv run --frozen python -m pytest tests/learner/contract_agent.py --learner-module learner_agent -q`，应12项通过；运行2.5事件探针，闭环输出应为`steps=2、observed=['C1']、stop_reason='final'`，缺结果与错配必须失败；运行4.3装配探针，半段参数、缺结束事件与提前闭合均零执行，完整流恰好执行一次。同时保存一条trace，显示C1只执行一次且结果进入第二轮消息。

**判定对错：** 真实执行、同call_id回填和停止边界都有证据才通过；猜对金额或最终文本正确不能替代观察。

<details>
<summary>完成预测后查看解释</summary>

删掉tool结果回传，却把最终答案硬编码为正确名称，算闭环通过吗？不算。测试应改变工具结果，确认第二轮消息和最终结果随之变化，而不只核对固定文本。

</details>

## 7. 面试问答与迁移

**问：工具描述属于授权吗？** 不属于。它只帮助模型提出请求；名称、参数、身份、预算和资源权限由程序检查。模型自带的tenant_id或“已批准”文字不能覆盖服务端上下文。

**问：怎样证明工具真的执行？** 用call_id关联请求与结果，再用业务调用记录或效果账本核对执行。模型自己说“已调用”不算；合法任务也不一定必须调用工具，应按任务契约判断。

**换条件自测：** 保持最终文本不变，让模型跳过必须查证的工具，验收应捕获证据缺失；再让工具超时，解释为何12步全绿仍未证明端到端时限。

## 8. 本章小结与参考

- 工具请求先校验再执行，可信身份不能由模型参数覆写。
- 结果按call_id回填，下一轮才能依据真实观察继续。
- steps、tool_calls、超时、总时限和费用预算分别计数与约束。
- 轨迹证明执行，最终文本碰巧正确不能替代证据。

第23章的证据链在这里增加受控动作；第25章把同一循环显式化为可暂停、可恢复的图。

官方参考：[Ollama Tool Calling](https://docs.ollama.com/capabilities/tool-calling)。动态框架版本以实际锁文件为准。

[上一章](23-项目实战一：DocPilot从零到检索系统.md) · [下一章](25-LangGraph、状态、Checkpoint与人工审核.md)
