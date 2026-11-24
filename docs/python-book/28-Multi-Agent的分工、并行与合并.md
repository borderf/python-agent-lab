# 第28章　Multi-Agent 的分工、并行与合并

[上一章](27-MCP与跨系统工具边界.md) · [全书目录](教材目录.md) · [下一章](29-原理面试：语言、工程与AI的追问.md)

## 1. 学习目标与前置知识

**本章为按需选修，第27章MCP不是前置。** 前置：第22章的同题评测、第24章的工具循环、第26章的ProcureAgent基线与故障记录。没有分工假设时，可以跳过本章，直接进入第29章。

**任务卡**
- **接收上一章什么产物：** 已完成主线时的P200规则报告、工具轨迹和效果账本；选修27时另有协议对照。
- **本章只新增什么：** 角色输入输出契约、受控并行和确定性合并，不改采购规则。
- **交付什么：** 单流程/单Agent与专家分工的同题对照，含局部超时和顺序反转。
- **怎样验收：** 发现不丢失、冲突不投票消失、超时标`partial`；质量、耗时和费用同口径，无收益可回退。

**本章从这里开始：** 仍用P200。单Agent已经找到超预算、预付款过高和证书过期；现在检查拆成预算、资格、合同三个角色，是否真的比一个角色更可靠或更快。

## 2. 基础知识讲解

### 2.1 先有基线，再决定是否分工

角色名称和提示份数不是能力证明。固定流程、单Agent、串行专家和并行专家都使用同一批题、身份、模型与总体预算。只有独立子任务、不同工具权限或上下文隔离确实解决问题时，分工才有候选价值。例如预算与资格可以独立读取，但合同结论若依赖预算结果，就必须等预算完成后再执行，不能为了并行提前运行。

| 组织模式 | 适用条件与机制 | 主要代价与反例 |
| --- | --- | --- |
| orchestrator-worker | 编排者动态分解、委派和复核异构任务，工作者按契约返回 | 编排者成为瓶颈；规划错误会扩散，依赖关系不能靠并行消除 |
| map-reduce | 先确定性切分独立输入，各mapper同构处理，再由一个reducer合并 | 跨文档依赖、共享写或需要反复协商时，预切分会产生假独立 |

`fan-out/fan-in`只描述分发与汇合，不自动等于多Agent。拆前先写清独立判据、权限差异、上下文收益和合并规则；若单Agent同题同预算已满足质量与延迟，就不拆。

### 2.2 共同契约让结果可以合并

每个角色返回`agent`、`status`、`findings`、`evidence_ids`和`incomplete`。发现使用稳定风险码，证据保留来源与规则版本。子Agent只获得必要材料和权限；跨领域事实通过明确摘要传递，不并发修改同一份消息列表。

**角色输入输出契约：** 用`task_id`、角色、输入快照摘要、Schema版本、允许工具、输出发现/证据/缺件、用量与局部状态描述每次委派。
- 输入只给该角色需要的字段与来源，输出拒绝额外字段和越权工具请求；编排者按契约校验，不能靠自然语言猜结果。
- 上下文隔离能减少提示注入、无关历史扩散和跨租户污染，也可降低单次token；代价是重复背景、事实快照不一致和协调成本。
- 跨角色传递最小结构化摘要并保留来源ID、租户、日期和规则版本；摘要不能覆盖原始证据，也不能替代依赖检查。

### 2.3 并行改变等待，不自动改变正确性

fan-out分发独立任务，fan-in等待并合并。一个角色超时，其空发现表示“未检查”，不是“无风险”。合并按稳定ID去重并保留冲突；评审返工要有次数、总时限和费用上限。取消父任务后要等待子任务清理，但已发出的外部写入仍需按效果账本核对。

**并行与重试预算：** 并行任务必须没有未声明的读写依赖、共享可变状态或顺序依赖；跨角色事实使用同一租户、日期和来源快照。
- 参数或证据校验失败不重试；只读超时可用原请求身份和时限重试；限流按次数、退避与抖动重试；写超时先查动作键，不盲目重放。
- 重试预算按“角色 attempts×fan-out×评审轮次”累计，并受全局截止时间、总token和费用约束；局部无限重试会耗尽整个任务。
- 确定性合并以租户、任务、风险码和证据版本为键：完全相同才去重，同风险码不同证据保留为冲突，缺失标`incomplete`，最后稳定排序。
- 合并不得采用最后写入覆盖、角色优先级或多数票消除冲突；完全相同的发现才去重，同码异证据全部保留，`conflicts`同时保存完整发现与证据ID，并按规范JSON稳定排序，顺序反转不改变结论。
- 取消采用协作式信号并等待子任务收尾；无法证明远端写入已停止时，保留未知状态并按动作键对账。

## 3. 原理讲解与推导

### 3.1 并行度增加后，完成顺序不能参与业务结论

分发只改变任务何时执行；合并必须根据角色、证据和状态确定结果。若合并采用“最后写入覆盖”，到达顺序就会改变风险集合。确定性的合并规则让局部失败可见，也让顺序反转成为有效测试。

**Evaluator防护与单Agent基线：** 评审只能提出可验证缺口，不能覆盖确定性规则或自行批准写动作。
- 初始上限可设2轮，并同时受总时限、token、费用和外部调用数限制；证据集合与风险码连续一轮无改进就停止。
- 停止时输出`partial/needs_review`、已发现项和未解决冲突，交人工复核；不能因为达到轮次上限把缺件改成通过。
- 对照必须同题、同输入快照、同模型与总预算，逐题记录正确/错误/未完成，再比较端到端p50/p95、最坏耗时、费用和复核率。
- 区分并行节省的等待与分工带来的质量收益；样本外推、重复运行波动和失败重试成本都要披露，无稳定收益就回退单Agent。

## 4. 示例与逐步走查

#### 案例推进：第一步，冻结单Agent的三项基线

P200在2026-10-01的基线是`OVER_BUDGET`、`PREPAYMENT_TOO_HIGH`、`EXPIRED_CERTIFICATE`。预算角色只看金额，资格角色只看证书，合同角色检查材料完整性。三者复用第26章的数据与规则，不重新解释制度。

#### 案例推进：第二步，并行执行并显式合并局部失败

下面让合同角色超时，其他两个角色返回结构化发现。合并器只对完全相同的发现去重，同风险码的不同证据全部保留，并把未完成角色列入`incomplete`。

```python
# study-example: S28A
import asyncio
import json

async def budget():
    await asyncio.sleep(0)
    return {"agent": "budget", "task_id": "T1", "tenant_id": "tenant-a", "status": "completed",
            "findings": [{"code": "OVER_BUDGET", "source_id": "P200",
                          "evidence_ids": ["P200"], "rule_version": "budget-v1"}],
            "evidence_ids": ["P200"], "incomplete": []}

async def qualification():
    await asyncio.sleep(0)
    return {"agent": "qualification", "task_id": "T1", "tenant_id": "tenant-a", "status": "completed",
            "findings": [{"code": "EXPIRED_CERTIFICATE", "source_id": "S200",
                          "evidence_ids": ["S200"], "rule_version": "qualification-v1"}],
            "evidence_ids": ["S200"], "incomplete": []}

async def contract():
    await asyncio.sleep(0)
    raise TimeoutError("合同材料查询超时")

def merge(parts):
    grouped, incomplete = {}, []
    for part in parts:
        if part["status"] != "completed":
            incomplete.append(part["agent"])
            continue
        for finding in part["findings"]:
            canonical = json.dumps(finding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            grouped.setdefault(finding["code"], {})[canonical] = finding
    findings, conflicts = [], []
    for code in sorted(grouped):
        variants = [grouped[code][key] for key in sorted(grouped[code])]
        findings.extend(variants)
        if len(variants) > 1:
            conflicts.append({
                "code": code,
                "findings": variants,
                "evidence_ids": sorted({item for finding in variants for item in finding["evidence_ids"]})
            })
    return {"status": "partial" if incomplete else "completed",
            "findings": findings, "conflicts": conflicts, "incomplete": sorted(incomplete)}

async def main():
    names = ["budget", "qualification", "contract"]
    values = await asyncio.gather(budget(), qualification(), contract(),
                                  return_exceptions=True)
    parts = [value if isinstance(value, dict) else
             {"agent": name, "task_id": "T1", "tenant_id": "tenant-a", "status": "timeout",
              "findings": [], "evidence_ids": [], "incomplete": [name]}
             for name, value in zip(names, values)]
    report = merge(parts)
    assert merge(list(reversed(parts))) == report
    assert report["status"] == "partial" and report["incomplete"] == ["contract"]
    assert report["conflicts"] == []
    assert [item["code"] for item in report["findings"]] == [
        "EXPIRED_CERTIFICATE", "OVER_BUDGET"]
    left = {"agent": "a", "task_id": "T1", "tenant_id": "tenant-a", "status": "completed", "findings": [
        {"code": "RISK", "source_id": "P200", "evidence_ids": ["P200"]}],
        "evidence_ids": ["P200"], "incomplete": []}
    right = {"agent": "b", "task_id": "T1", "tenant_id": "tenant-a", "status": "completed", "findings": [
        {"code": "RISK", "source_id": "P201", "evidence_ids": ["P201"]}],
        "evidence_ids": ["P201"], "incomplete": []}
    left_finding, right_finding = left["findings"][0], right["findings"][0]
    conflicted = merge([left, right])
    assert conflicted["findings"] == [left_finding, right_finding]
    assert conflicted["conflicts"] == [{
        "code": "RISK", "findings": [left_finding, right_finding],
        "evidence_ids": ["P200", "P201"]}]
    assert merge([right, left]) == conflicted
    print(json.dumps(report, ensure_ascii=False))

asyncio.run(main())
```

预期输出保留两项已完成发现，整体为`partial`，指出合同审查未完成，且`conflicts`为空；额外反例证明同风险码的不同证据会同时保留在`findings`和结构化`conflicts`中，反转输入顺序不改变结果。它没有证明真实模型专家更准确，也没有实现全局时限或生产资源隔离。

#### 案例推进：第三步，用同题对照决定是否保留分工

| 方案 | 必须记录 | 本轮示例能说明什么 |
| --- | --- | --- |
| 单Agent基线 | 三项发现、总步数与耗时 | 完整覆盖P200预设检查 |
| 并行专家 | 角色轨迹、局部状态、总费用 | 合同超时时只保留两项发现 |
| 并行加评审 | 返工原因、轮次与停止条件 | 防止无限要求补证据 |

把P300换成缺资料案例，再把合同角色改为返回旧制度证据。合并应保留缺件与版本冲突，不能靠多数票改成通过。比较时先看同一道题是否从错误变正确，再看端到端延迟和总费用；批量平均可能掩盖长尾，因此还要保留单题最坏耗时与失败原因。若分工没有质量或延迟收益，就保留单Agent。

## 5. 动手练习

### 本章累计任务：用基线约束多角色

在同一批采购题上比较单流程/单Agent与专家分工，注入一次合同超时并反转完成顺序。提交共同输出契约、逐题结果和`multi_agent_comparison.json`，记录质量、调用数、token、延迟与复核率；总预算和返工轮次受限。材料复用[第26章](26-项目实战二：ProcureAgent审查系统.md)，评测口径见[第22章](22-AI评测、提示注入、追踪与成本.md)。

## 6. 验收与自测

**验收产物：** 一份`multi_agent_comparison.json`。每个案例包含基线结果、分工结果、完成顺序、局部失败、用量和是否采用；另附一次顺序反转后结果不变的轨迹。

### 6.1 先预测，再查看参考推导

上例证明了什么，尚未证明什么？

<details>
<summary>完成预测后查看解释</summary>

它证明指定组织方式能保留成功结果、表达局部失败，并使合并不受到达顺序影响。它没有证明真实模型专家的质量更高、证据相互独立或成本更低，这些要用同题同预算实验证明。

</details>

## 7. 面试问答与迁移

**问：什么任务值得拆Agent？**
答：独立子任务可并行、工具权限不同或上下文需要隔离，并且有可测收益时。先写角色输入、产物和合并规则，再与单Agent比较；角色数量本身不是收益。

**问：两个专家引用不同制度版本，怎样合并？**
答：先按任务日期、租户和来源权限判断适用性，再保留冲突及证据。不能因为回答更自信或篇幅更长就选择其中一个，也不能用多数票改写事实。

**问：怎样避免评审无限返工？**
答：设置最大轮次、总时限、费用和无改进停止条件。主执行者与评委可能同错，循环更多次不会自动变真；最终保留证据并交人工复核。

## 8. 本章小结与参考

- 分工改变信息组织，并行改变时间安排；两者都要与单Agent同题同预算比较。
- 共同Schema、稳定风险码和证据ID让局部结果可合并。
- 超时角色的空发现不是无风险；整体必须标记`partial`或`needs_review`。
- 合并不得依赖到达顺序，也不得用投票消除证据冲突。
- 没有实测收益就回退简单方案，把对照证据带到[第29章](29-原理面试：语言、工程与AI的追问.md)。

参考：[LangGraph概览](https://docs.langchain.com/oss/python/langgraph/overview)、[评测与故障演练](../project-practice/评测与故障演练.md)。框架版本以锁文件为准。

[上一章](27-MCP与跨系统工具边界.md) · [下一章](29-原理面试：语言、工程与AI的追问.md)
