# 第26章　项目实战二：ProcureAgent 审查系统

[上一章](25-LangGraph、状态、Checkpoint与人工审核.md) · [全书目录](教材目录.md) · [下一章](27-MCP与跨系统工具边界.md)

## 1. 学习目标与前置知识

前置：第16章的审批与幂等、第22章的评测、第24章的工具循环、第25章的任务恢复。本章不要求先学MCP或多Agent。

**任务卡**
- **接收上一章什么产物：** 第25章保存、批准、冻结载荷和跨进程恢复的任务状态机。
- **本章只新增什么：** 把采购只读工具、确定性规则和脚本化模型循环接到同一状态机。
- **交付什么：** ProcureAgent离线审查、工具轨迹、审批记录和一次失回执恢复记录。
- **怎样验收：** P200得到三项风险；P300保留缺资料；拒绝或改载荷零写入；同一动作恢复后业务效果一次。

**本章从这里开始：** 从头到尾只处理同一份采购审查请求：`P200 / tenant-a / 2026-10-01`。先让规则算对，再让模型选工具，最后单独检查批准与写入效果。

## 2. 基础知识讲解

### 2.1 审查结论、流程状态与业务效果是三种事实

规则可以发现超预算，模型可以组织工具调用，批准可以授权提交，但三者不能互相证明。`completed`只表示约定检查已执行；缺资料应返回`needs_review`，不能把“没查到风险”写成合规。

**威胁模型与信任边界：** 文档字段、模型输出和用户点击都可被伪造；身份、授权与业务事实只能来自认证会话、可信工具和审批服务，不能由模型自报。
| 边界 | 信任假设 | 必须检查 |
| --- | --- | --- |
| 文档与模型 → 审查器 | 内容可能含提示注入或旧数据 | 字段来源、租户、业务日期、规则版本；注入不得改写金额或权限 |
| 审查器 → 工具 | 模型可提议，不可授予身份 | 工具与参数白名单；服务端再次授权；只读工具不得绕过写路径 |
| 批准 → 执行器 | 审批记录由可信服务保存 | 审批人、有效期、报告版本和载荷快照；页面显示不等于已签发 |
| 执行器 → 接收方 | 网络会重复、乱序或丢回执 | 租户、稳定动作键、幂等冲突和真实效果核对 |

提示注入的目标是改变后续模型行为，不是获得系统权限；把工具输出标记为不可信数据、限制工具权限并让确定性程序作最终判断，才能阻断“文本→动作”的越权链路。

### 2.2 事实与规则由可信程序提供

项目金额、供应商证书和制度版本来自模拟业务服务。模型只能提出工具请求，不能填写预算、租户、日期或付款上限。规则输出风险码、缺件码、来源ID和制度版本，便于复算。

#### 案例推进：先建立可复算的规则基线

```python
# study-example: S26A
def review(facts):
    findings, missing = [], []
    if facts["quote_cents"] > facts["budget_cents"]:
        findings.append("OVER_BUDGET")
    if facts["prepayment_percent"] is None:
        missing.append("MISSING_PREPAYMENT")
    elif facts["prepayment_percent"] > facts["limit_percent"]:
        findings.append("PREPAYMENT_TOO_HIGH")
    return {"status": "needs_review" if missing else "completed",
            "findings": findings, "missing": missing}
result = review({"quote_cents": 1100, "budget_cents": 1000,
                 "prepayment_percent": None, "limit_percent": 20})
assert result == {"status": "needs_review", "findings": ["OVER_BUDGET"],
                  "missing": ["MISSING_PREPAYMENT"]}
```

### 2.3 工具循环只负责取得证据

采购工具注册表与第24章订单注册表分开，避免破坏“恰好两个订单工具”的旧契约。每轮依次做模型提议、参数校验、可信身份下执行、结果回填；未知工具和坏参数在业务调用前拒绝，步数与时限要有上限。

### 2.4 批准、幂等与恢复各自解决一个窗口

批准绑定报告版本与载荷摘要；修改载荷后旧批准失效。拒绝、过期或未批准时写入0次。接收方按租户和稳定动作键去重，同键同载荷返回原回执，同键换载荷报冲突。远端提交后本地丢回执时，用原键查询或重试并核对效果数，不能换键盲写。取消等待或关闭连接不等于远端效果已经停止。

**审批绑定必须覆盖动作身份：** 可信审批记录至少绑定`tenant_id/task_id/action_key`、审批人、有效期、报告版本和`payload_hash`，并在执行时检查是否已使用或撤销。
- 载荷摘要对 canonical JSON计算：固定Schema、键排序、金额用整数分、日期用统一格式；不能哈希展示后可继续修改的字典。
- 摘要覆盖项目、收款方、金额、币种、付款日期、载荷版本等全部生效字段；任何字段改变都生成新动作和新批准。
- Hash只用于完整性比较，不是签名；审批记录必须存放在模型不可写的可信存储，执行器重新读取，不能信任请求里夹带的`approved=true`。
- 同键同载荷可重放已批准动作，同键换载荷必须冲突；批准过期、任务改派或动作已执行都不能悄悄复用旧授权。

UI预览、审批签发和动作执行是三个时刻；只有签发时冻结的快照与执行时重新计算的摘要一致，批准才有效。

## 3. 原理讲解与推导

### 3.1 把决策记录与效果账本分开，才能定位失败

同一请求依次产生三种记录：模型选了什么、任务停在哪一步、接收方实际产生了什么效果。规则错误只污染结论，模型错误只污染工具轨迹，恢复错误可能增加业务效果。分别保存这三种记录，故障注入才能指出第一个分叉，而不是用“任务已完成”掩盖重复写入。

**效果账本与对账：** 账本字段包括租户、任务、动作键、载荷摘要、请求ID、接收方回执、效果数与时间；调用前先写意图并预留未知状态，后续按回执更新。本地`completed`只是决策状态，不是效果证据。
- 丢回执后先保持`unknown`，用原键查询或同键同载荷重试；未知状态不能自动改成失败，也不能新建动作键。
- 对账比较意图、回执和效果账本的租户、动作键、载荷摘要与数量；缺失、重复或不一致分别进入补单、阻止重放和人工处理。
- “恰好一次业务效果”需要接收方把唯一键与效果放在同一事务；若外部副作用无法入事务，只能证明至少一次投递，并用查询、幂等或业务补偿收敛结果。

**审计不可篡改是有边界的：** 应用账号只可追加、禁止更新删除，敏感载荷脱敏，并用Hash链、独立WORM存储或外部锚点检测事后改写。Hash链只有在链头、签名密钥或锚点由可信边界保管时才有意义；若攻击者能改写同库账本并重算整条链，就不能靠它发现篡改。WORM也需要独立权限边界。这些措施能发现篡改，不能阻止拥有数据库或签名密钥的特权管理员。审计证明“记录过什么”，业务效果仍以接收方账本和业务系统为准。

**能力边界：** 本章离线示例验证规则、脚本循环与SQLite恢复参考；真实模型、MCP、LangGraph跨进程恢复、真实远端和多Agent均未因此获得运行证据，生产认证、并发与灾备也未验收，材料中必须标为未完成或设计假设。

## 4. 示例与逐步走查

固定输入来自[项目数据](../../practice/enterprise_ai/data/projects.json)：P200报价12000000分、预算10000000分、预付款25%；S200证书在2026-09-01到期。当前制度上限20%，因此预期风险为`OVER_BUDGET`、`PREPAYMENT_TOO_HIGH`、`EXPIRED_CERTIFICATE`。

#### 案例推进：第一步，用同一请求跑通工具循环

下面用脚本替身压缩展示循环。它从真实数据文件取事实；接真实模型时仍使用第24章的决策解析、调用ID和预算检查。

```python
# study-example: S26B
import json
from practice.enterprise_ai.policy_agent import lookup_limit
from practice.enterprise_ai.retrieval_baseline import DATA
tenant = "tenant-a"
data = {name: json.loads((DATA / f"{name}.json").read_text(encoding="utf-8")) for name in ("projects", "suppliers", "policies")}
def only(name, key, value):
    matches = [row for row in data[name] if row["tenant_id"] == tenant and row[key] == value]
    if len(matches) != 1: raise LookupError("resource unavailable")
    return matches[0]
def get_project(project_id):
    row = only("projects", "project_id", project_id)
    return {k: v for k, v in row.items() if k != "tenant_id"}
def get_supplier(supplier_id):
    row = only("suppliers", "supplier_id", supplier_id)
    return {k: v for k, v in row.items() if k != "tenant_id"}
def get_policy(as_of):
    return lookup_limit(data["policies"], tenant, as_of)
def review(project_id, as_of):
    results, trace = {}, []
    for name in ("get_project", "get_supplier", "get_prepayment_limit"):
        if name == "get_project":
            arguments = {"project_id": project_id}
        elif name == "get_supplier":
            arguments = {"supplier_id": results["get_project"]["supplier_id"]}
        else:
            arguments = {}
        function = {"get_project": get_project, "get_supplier": get_supplier,
                    "get_prepayment_limit": get_policy}[name]
        result = function(as_of=as_of, **arguments) if name == "get_prepayment_limit" else function(**arguments)
        results[name] = result
        source_id = (result.get("source_id") or arguments.get("project_id")
                     or arguments.get("supplier_id"))
        trace.append({"tool": name, "source_id": source_id, "arguments": arguments})
    project, supplier, rule = (results[name] for name in ("get_project", "get_supplier", "get_prepayment_limit"))
    findings, incomplete = [], []
    if project["quoted_amount_cents"] > project["budget_cents"]:
        findings.append("OVER_BUDGET")
    if project["prepayment_percent"] is None:
        incomplete.append("prepayment_percent")
    elif project["prepayment_percent"] > rule["limit_percent"]:
        findings.append("PREPAYMENT_TOO_HIGH")
    if supplier["certificate_valid_until"] is None:
        incomplete.append("certificate_valid_until")
    elif supplier["certificate_valid_until"] < as_of:
        findings.append("EXPIRED_CERTIFICATE")
    report = {"project_id": project_id, "supplier_id": supplier["supplier_id"], "as_of": as_of,
              "status": "needs_review" if incomplete else "completed", "findings": findings,
              "incomplete": incomplete, "policy_source_id": rule["source_id"]}
    return report, trace
report, trace = review("P200", "2026-10-01")
assert report["findings"] == ["OVER_BUDGET", "PREPAYMENT_TOO_HIGH", "EXPIRED_CERTIFICATE"]
assert report["policy_source_id"] == "policy-a-current"
assert [item["source_id"] for item in trace] == ["P200", "S200", "policy-a-current"]
old_report, _ = review("P200", "2026-06-01")
assert old_report["findings"] == ["OVER_BUDGET"]
missing_report, missing_trace = review("P300", "2026-10-01")
assert missing_report["status"] == "needs_review"
assert missing_report["incomplete"] == ["prepayment_percent", "certificate_valid_until"]
assert [item["source_id"] for item in missing_trace] == ["P300", "S300", "policy-a-current"]
print(json.dumps({"report": report, "trace": trace}, ensure_ascii=False))
```

预期输出包含三项风险和依次执行的三个工具，轨迹中的来源ID分别为P200、S200和制度来源。若最终文本碰巧正确但轨迹缺工具证据，工具使用仍判失败。把日期改为2026-06-01，应使用旧制度且证书有效，只剩超预算；把项目改为P300，应动态查询其供应商S300，预付款与证书为空并进入`needs_review`。

#### 案例推进：第二步，把报告放进受批准的写入动作

以下直接调用仓库的[审批接收方](../../practice/learning_projects/approval_reference.py)和[恢复参考](../../practice/learning_projects/resume_reference.py)。`approved_hash`是可信批准边界的输入，示例本身不实现登录、签发或撤销。

```python
# study-example: S26C
from contextlib import closing
from pathlib import Path
import json, sqlite3
from tempfile import TemporaryDirectory
from practice.learning_projects import resume_reference as resume
def effect_count(path):
    if not path.exists(): return 0
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT count(*) FROM effects").fetchone()[0]
def rejected(call):
    try:
        call()
    except PermissionError: return
    raise AssertionError("unapproved or stale write must fail")

with TemporaryDirectory() as directory:
    tasks, effects = Path(directory) / "tasks.sqlite", Path(directory) / "effects.sqlite"
    scope = {"tenant_id": "tenant-a", "task_id": "R1"}
    send = lambda version, **kw: resume.resume(tasks, effects, expected_version=version, **scope, **kw)
    approve = lambda task: resume.approve(tasks, expected_version=task["version"], expected_hash=task["payload_hash"], **scope)
    payload = {"project_id": "P200", "version": 1, "findings": ["OVER_BUDGET", "PREPAYMENT_TOO_HIGH", "EXPIRED_CERTIFICATE"]}
    task = resume.prepare(tasks, payload=payload, **scope)
    rejected(lambda: send(1))
    assert effect_count(effects) == 0
    task = approve(task)
    changed = resume.change_payload(tasks, expected_version=1,
                                    payload={**payload, "version": 2}, **scope)
    assert changed["approved_hash"] is None
    rejected(lambda: send(2))
    assert effect_count(effects) == 0
    approve(changed)
    try:
        send(2, fail_after_commit=True)
    except RuntimeError as error:
        assert "after commit" in str(error)
    else:
        raise AssertionError("lost reply must be injected")
    receipt = send(2)
    assert send(2) == receipt and effect_count(effects) == 1
    status = resume.load(tasks, **scope)["status"]
    print(json.dumps({"status": status, "business_effects": effect_count(effects)}, ensure_ascii=False))
```

预期输出为`completed`和1次业务效果。恢复必须核对接收方账本；只把本地状态改成completed不能证明写入正确。

#### 案例推进：第三步，用故障记录决定下一步复杂度

保留正常、缺资料、历史日期、越权、未知工具、批准拒绝、改载荷和失回执八类记录。只有确实需要跨进程共享或专家分工时，才进入第27–28章；它们不是ProcureAgent主路径的前置。

## 5. 动手练习

### 本章累计任务：组合受控审查

在同一份P200请求上完成确定性基线、采购工具循环和审批恢复。保留`report.json`、`trace.jsonl`、任务状态与效果账本；用P300证明缺资料不伪造通过，用失回执证明恢复不增加效果。旧订单契约继续通过，采购工具使用独立注册表。真实模型、LangGraph跨进程恢复和真实远端分别记录验证范围，不能用离线替身结果代替。

## 6. 验收与自测

**验收产物：** 上述报告、轨迹和效果数；再运行一次可重复的提示版本比较。

### 先为一个真实工具建立可重复的版本比较

```powershell
uv run --frozen python -m practice.enterprise_ai.policy_agent --compare --trials 2
```

命令固定三道日期题、工具和评分规则，逐行输出JSON，末行汇总每种提示的通过数与尝试数。替身下每个提示为6/6，只证明执行器与评分器配合；真实模型比较与用量记录见[评测与故障演练](../project-practice/评测与故障演练.md)。

### 6.1 先预测，再查看参考推导

`completed`是否等于“采购合规”？

<details>
<summary>完成预测后查看解释</summary>

不等于。它只表示当前约定的检查执行完毕。缺资料需要复核，预设风险需要处置，真实写入还要核对业务效果；这些结论不能互相替代。

</details>

## 7. 面试问答与迁移

**问：远端已经提交但本地没有回执，为什么不能直接换一个动作键重试？**
答：新键会绕过接收方去重，可能产生第二次效果。应先冻结载荷，用原租户和动作键查询或同键同载荷重试；接收方不支持这些契约时，保留未知状态并对账或交人工处理。
**问：审批通过后修改报告，或用户取消等待，分别意味着什么？**
答：修改报告使原批准失效，必须重新批准；取消本地等待只停止本地调度，不保证已经发出的远端写入停止，仍需查询动作状态和实际效果。

## 8. 本章小结与参考

- 主线是“可信事实 → 工具轨迹 → 确定性结论 → 批准与效果核对”，不是堆叠框架。
- P200用于完整正例，P300用于缺资料反例；日期变化必须重新选择制度版本。
- 审批绑定载荷，幂等绑定租户与动作键，恢复核对真实效果，三者缺一不可。
- 第27–28章按需选修；没有共享或分工问题时，直接进入[第29章](29-原理面试：语言、工程与AI的追问.md)整理作品证据。

参考：[LangGraph持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、[审批与幂等契约](../../tests/learner/练习说明.md#审批与幂等契约)。框架版本以实践时的锁文件为准。

[上一章](25-LangGraph、状态、Checkpoint与人工审核.md) · [下一章](27-MCP与跨系统工具边界.md)
