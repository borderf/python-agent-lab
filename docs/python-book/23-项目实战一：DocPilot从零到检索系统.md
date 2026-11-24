# 第23章　项目实战一：DocPilot 从零到检索系统

[上一章](22-AI评测、提示注入、追踪与成本.md) · [全书目录](教材目录.md) · [下一章](24-ToolCalling与手写AgentLoop.md)

## 1. 学习目标与前置知识

前置：第15–22章，重点补第16–17章的幂等、故障恢复与测试边界。把前文组合成可演示、可评测的DocPilot。

**本章任务卡**

- **接收：** 第18–20章的文档、权限与检索能力，以及第21–22章的逐题评测口径。
- **只新增：** 从空文件累计的规范化、分块、过滤检索、引用回答核心，再以适配器接HTTP与持久化。
- **交付：** `learner_docpilot.py`、20步契约结果、HTTP请求记录和可重启查询的持久化适配器。
- **验收：** 四段代码依次拼接通过20步契约；HTTP不重写业务；换租户、日期和新资料仍正确；来源打开与查询继续受权限约束。

**承接与本章主线：** 同一份原文依次经过规范化、索引、过滤、检索和回答。任何失败都沿中间产物定位，不先换模型。完成查证型核心后，需要执行动作再进入第24章。

**本章从这里开始：** 用户上传文档、提问并核对来源。每个中间对象都带身份和定位，才能解释答案属于谁、依据在哪一版。

## 2. 基础知识讲解

### 2.1 用中间对象连接全链路

Document保存来源、租户、版本、权限与生效区间；Chunk保存正文片段、稳定ID和偏移；Citation把回答连回本次证据。字段抽取与证据问答都先限定文档类型、用户范围、日期和失败行为。

模块边界可划为输入规范化、索引构建、过滤检索、回答校验四个纯核心，HTTP/仓储/模型通过适配器注入；核心不读环境变量、不发请求，适配器不复制排序与引用规则。这样20步契约可离线跑，替换持久化时仍能复用同一行为基线；若业务函数开始直接依赖框架请求对象，迁移条件就已改变。
一次查询保留身份、候选、实际上下文、回答和引用。最终文本错误时，依次检查解析、版本过滤、召回排序与生成使用证据，找第一个分叉。可观察清单至少记录request_id、语料/索引/模型版本、过滤前后数量、候选ID与分数、实际上下文ID、引用和失败阶段；文本可按权限截断或脱敏，但定位标识与计数必须能关联，不能只留最终答案。

#### 案例推进：让来源身份贯穿数据流

用户问“预付款上限”，先确认文档属于当前租户且当日有效，再进入排名。chunk_id包含租户、来源、版本和起点，引用才能回到特定位置；偏移是规范化文本的码点位置，不是PDF页码。

### 2.2 按可运行版本推进

采用[项目装配页的D1–D4](../project-practice/从实验到项目交付.md#docpilot-采用同一套版本顺序)：D1用字面检索完成可过滤问答；D2接数据库、HTTP接口、引用与反馈；D3换真实模型和向量；D4完成部署、故障与用户验收。

每版保留同一组回归。新增组件必须说明解决哪类失败，不在第一版同时部署模型、向量库、数据库和界面。

需求追踪要落到20步，不只写“检索完成”：下列分组中的每个步骤都保留输入、预期、实际结果和契约编号；新增需求先映射到某步的正例或反例，不能悄悄改通过标准。

| 步骤 | 需求与验收证据 | 步骤 | 需求与验收证据 |
| --- | --- | --- | --- |
| 1–2 | 七字段严格校验、日期与左闭右开区间 | 12 | 确定性同分排序与独立副本 |
| 3–4 | 稳定chunk_id、规范化文本码点偏移 | 13–14 | 仅传本次证据副本、无证据不调用模型 |
| 5–6 | 可重复索引、同版本重复与内容冲突 | 15–18 | 结构、引用范围、逐字quote、去重与复核标记 |
| 7–8 | 可信租户与业务日期过滤 | 19–20 | 模型异常不吞、快照隔离、跨请求无残留 |
| 9–11 | 字符二元组基线、正整数limit、无公共词项返回空 | 汇总 | 20项独立通过，失败能回到对应步骤 |

#### 案例推进：先完成最小核心，再接外部系统

本章四段累计代码只使用标准库：等长分块与字符二元组检索是可手算基线，不冒充语义检索。先通过20步契约，再用适配器替换模型或存储，业务函数签名不变。

### 2.3 交付必须包含证据与限制

启动说明、固定题集、数据与模型版本、逐题结果、失败复现和已知限制都是交付物。演示正常、无证据、历史版本和越权四类请求，不只播放成功聊天。

索引是派生数据，更新、重建和版本映射要可复现。异步导入需要可查询状态，不能让浏览器无限等待；界面可以后加，服务与契约先稳定。

#### 案例推进：用失败演示解释架构

展示一条正常请求的文档、块、候选、答案与引用，再制造旧版排前或解析错误，沿中间产物定位并重跑。未支持格式、真实语义检索和部署能力要明确标为尚未验证。

失败矩阵应固定复现输入、注入点和预期安全行为，不只记录“回答不好”：

| 失败 | 首要观察 | 验收边界 |
| --- | --- | --- |
| 解析缺失/重复 | 原文→Document→Chunk的数量与偏移 | 不静默吞错，同版本冲突可定位 |
| 权限/版本过滤错误 | 过滤前后ID与身份、日期 | 越权结果为零，不能靠后置删除掩盖 |
| 检索漏召回/旧版靠前 | 候选池、分数、版本与标准证据位置 | 先修过滤或召回，再谈重排 |
| 引用存在但不支持结论 | quote所在块与结论中的数值、条件 | 位置通过仍判语义失败 |
| 模型异常/坏结构/超时 | 原异常、输出结构与错误映射 | 不伪造答案，不吞异常或无限重试 |
| 重启/并发更新 | 提交版本、查询快照、索引版本 | 不串请求，不用永久缓存掩盖新资料 |

演示证据是一条可复跑的批次：命令与环境、固定请求、各阶段产物、20步结果、HTTP状态及重启前后查询。截图只辅助说明，不能替代原始输出；正常、无证据、旧版、越权与故障至少各一条，并明确哪些尚未验证。

## 3. 原理讲解与推导

### 3.1 有损转换需要逐阶段验证

解析、切块、过滤和截断都可能丢失或改变信息。为每步保留输入、输出标识和定位，才能验证当前组件是否忠实；否则最终回答出错时，只能盲目替换更大的模型。

从内存迁到HTTP只改变传输与可信身份入口，不改变纯核心；迁到持久化才引入事务、并发、快照一致性、索引失效和迁移成本。先确认单次查询是否绑定同一已提交语料版本，再决定何时重建索引；提交后立即可见与强一致快照不能同时凭空保证。若改成异步导入或语义检索，要新增可见性状态、模型/索引版本和评测基线，而不是宣称原20步契约已覆盖生产行为。

## 4. 示例与逐步走查

### 4.1 从空文件开始同一查询

新建 `learner_docpilot.py`。四段累计代码依次写入同一文件，后段调用前段函数，不能当作独立示例。统一问题是“预付款比例是多少”，统一检查租户a在2026-07-01的可见证据。

先实现并预测每步结果，再运行到当前步骤号：

```powershell
uv run --frozen python -m pytest tests/learner/contract_docpilot.py --learner-module learner_docpilot --through-step 1 -q
```

较后步骤显示deselected，不是通过。参考模块只能证明验收器可用，自己的完成证据必须保留实际模块名。[完整契约与失败定位](../../tests/learner/练习说明.md)

### 4.2 步骤1–6：让资料成为可靠输入

步骤1规范化七字段并拒绝额外字段；步骤2把日期规范成YYYY-MM-DD，区间为左闭右开。步骤3–6建立稳定片段身份、码点偏移、可重复索引，并区分同版本重复与内容冲突。

```python
from copy import deepcopy
from datetime import date
import json

def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()

def _date(value):
    if not isinstance(value, str):
        raise ValueError("date must be ISO text")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return value

def normalize_document(raw):
    fields = {"source_id", "tenant_id", "version", "title", "text", "valid_from", "valid_to"}
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ValueError("unexpected document fields")
    result = {key: _text(raw[key], key) for key in fields - {"valid_from", "valid_to"}}
    result["valid_from"] = _date(raw["valid_from"])
    result["valid_to"] = None if raw["valid_to"] is None else _date(raw["valid_to"])
    if result["valid_to"] is not None and result["valid_to"] <= result["valid_from"]:
        raise ValueError("invalid validity interval")
    return result
```

`chunk_chars`必须是1以上的真正整数，布尔值拒绝。相同租户、来源、版本和内容只建一次；不同内容报错，不覆盖成“最新”。不同租户允许同名来源。

```python
def build_index(documents, chunk_chars=120):
    if type(chunk_chars) is not int or chunk_chars < 1:
        raise ValueError("chunk_chars must be a positive integer")
    sources = {}
    for raw in documents:
        document = normalize_document(raw)
        key = (document["tenant_id"], document["source_id"], document["version"])
        if key in sources and sources[key] != document:
            raise ValueError("same source version has different content")
        sources[key] = document
    chunks = []
    for key, document in sorted(sources.items()):
        for start in range(0, len(document["text"]), chunk_chars):
            end = min(start + chunk_chars, len(document["text"]))
            # JSON encoding avoids collisions caused by delimiters inside IDs.
            chunk_id = json.dumps([*key, start], ensure_ascii=False, separators=(",", ":"))
            chunks.append({**document, "text": document["text"][start:end],
                           "start": start, "end": end, "chunk_id": chunk_id})
    return chunks
```

### 4.3 步骤7–12：先限制范围，再排序

步骤7–8先按可信租户和业务日期过滤；步骤9用问题与标题、正文的公共字符二元组数打分；步骤10把limit限制为1–10的整数。无公共词项返回空，不凑满Top-K。步骤12同分按来源、版本、起点排序，并返回独立副本。

```python
def _terms(text):
    normalized = "".join(text.lower().split())
    return {normalized[i:i + 2] for i in range(len(normalized) - 1)}

def search(index, question, *, tenant_id, as_of, limit=3):
    question = _text(question, "question")
    tenant_id = _text(tenant_id, "tenant_id")
    as_of = _date(as_of)
    if len(question) < 2 or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("question too short or limit outside 1..10")
    query_terms = _terms(question)
    scored = []
    for chunk in index:
        if chunk["tenant_id"] != tenant_id:
            continue
        if chunk["valid_from"] > as_of or (chunk["valid_to"] is not None and as_of >= chunk["valid_to"]):
            continue
        score = len(query_terms & _terms(chunk["title"] + chunk["text"]))
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda row: (-row[0], row[1]["source_id"], row[1]["version"], row[1]["start"]))
    return [deepcopy(chunk) for _, chunk in scored[:limit]]
```

先画“过滤前→过滤后→排名→截断”。如果本租户结果消失，先查它是否在截断前被错误排除，不要马上换模型。

### 4.4 步骤13–20：让模型成为受检验的候选来源

步骤13只把本次可见证据副本交给 `model(question, evidence)`；步骤14无证据时不调用模型，直接返回待复核。步骤15–18严格检查候选结构、本次引用、逐字quote、重复项和复核标记。步骤19保留可信快照并上抛模型异常；步骤20交替查询不同租户与日期，检查没有跨请求残留。

```python
def answer(index, question, *, tenant_id, as_of, model):
    evidence = search(index, question, tenant_id=tenant_id, as_of=as_of)
    if not evidence:
        return {"answer": "当前可访问资料中没有找到依据。", "citations": [], "needs_review": True}
    # Keep the trusted evidence independent of a callback's mutable arguments.
    generated = model(question, deepcopy(evidence))
    if not isinstance(generated, dict) or set(generated) != {"answer", "citations", "needs_review"}:
        raise ValueError("unexpected answer fields")
    text = _text(generated["answer"], "answer")
    if type(generated["needs_review"]) is not bool or not isinstance(generated["citations"], list):
        raise ValueError("invalid review flag or citations")
    by_id = {chunk["chunk_id"]: chunk for chunk in evidence}
    citations, seen = [], set()
    for citation in generated["citations"]:
        if not isinstance(citation, dict) or set(citation) != {"chunk_id", "quote"}:
            raise ValueError("unexpected citation fields")
        chunk_id, quote = citation["chunk_id"], citation["quote"]
        if not isinstance(chunk_id, str) or chunk_id not in by_id:
            raise ValueError("citation outside evidence")
        if not isinstance(quote, str) or not quote.strip() or quote not in by_id[chunk_id]["text"]:
            raise ValueError("quote absent from source")
        if (chunk_id, quote) in seen:
            raise ValueError("duplicate citation")
        seen.add((chunk_id, quote))
        chunk = by_id[chunk_id]
        citations.append({**citation, "source_id": chunk["source_id"], "version": chunk["version"],
                          "start": chunk["start"], "end": chunk["end"]})
    if not citations and not generated["needs_review"]:
        raise ValueError("uncited answer must require review")
    return {"answer": text, "citations": citations, "needs_review": generated["needs_review"]}
```

20步通过只证明输入输出与失败分支符合约定，不证明真实语义检索、引用支持结论、HTTP入口认证或生产性能。

### 4.5 将同一个核心接到HTTP，而不是重写业务

先通过自己的20步契约，再设置模块名并启动同一HTTP工厂：

```powershell
uv sync --frozen --group web --inexact
$env:LEARNER_MODULE = 'learner_docpilot'
uv run --frozen --group web uvicorn practice.learning_projects.service:create_app --factory --host 127.0.0.1 --port 8011
```

打开 `http://127.0.0.1:8011/docs`，用教学令牌demo-a或demo-b向 `/api/questions` 发送question“预付款”和as_of“2026-07-01”。换历史日期与另一令牌核对结果。请求体不允许自报tenant_id；该切片使用内存索引和替身，重启会重建，不是完整登录系统。

[HTTP适配器](../../practice/learning_projects/service.py)只处理请求模型、可信教学身份和错误映射：超时504、坏模型输出502、无证据是正常复核结果。业务仍调用自己的四个函数。接真实模型时重新跑同一组行为，不把模式切换藏进默认回退。

### 4.6 把同一核心接到持久化

数据库保存已提交原文事实，适配器负责字段映射，核心继续负责规范化、索引、检索和回答。先跑[6步持久化契约](../../tests/learner/练习说明.md)，再把核心与适配器同时注入HTTP工厂；参考D2不会自动导入你的四个函数。

迁移按五步推进：

1. 保持20步函数签名并通过原契约；仓储从[起始签名](../../practice/learning_projects/persistence_starter.py)实现。
2. 查询先按可信租户读取已提交原文，再调用注入核心的 `build_index` 和 `search`；不能启动时读一次后永久缓存。
3. 上传执行“校验→持久提交→返回来源与版本”。当前每次查询重建，生产版本化索引与失效策略另行测量。
4. 写入后不重启查询，再重启查询，核对日期、租户和引用；新来源立即可见。
5. 再接来源打开、反馈、真实模型、向量和部署。来源打开重新授权，不能凭chunk_id直接返回原文。

[项目装配：把20步核心带到持久服务](../project-practice/从实验到项目交付.md#把20步核心带到持久服务) · [项目里程碑与交付检查](附录E-项目里程碑与交付检查.md)

## 5. 动手练习

### 本章累计任务：从空文件完成DocPilot核心与适配

按4.2–4.4写自己的模块，逐步通过20步契约；用一份新资料和另一组日期重做。再按4.5接HTTP、按4.6接持久化，保存正常、无证据、旧版、越权和重启后的查询记录。

**未通过时怎样定位：** 参考基线通过不是自己的证据；引用位置正确不证明语义支持；内存HTTP通过不证明持久化；教学令牌不是真实登录。

**带到下一步：** 查证型任务可在此交付；需要选择并执行工具时进入第24章。

## 6. 验收与自测

**验收命令与产物：** 运行 `uv run --frozen python -m pytest tests/learner/contract_docpilot.py --learner-module learner_docpilot -q`，应20项通过；再交付一条HTTP正常请求、一条越权请求和一条持久化写入后重启仍可查的记录。

<details>
<summary>完成预测后查看解释</summary>

最终答案错了，首先应该换更大模型吗？先沿解析、权限过滤、召回、排序、上下文和生成定位，判断证据在哪一步丢失或误用。只有证据支持模型瓶颈时，换模型才是可检验的改进。

</details>

## 7. 面试问答与迁移

**问：怎样证明DocPilot不是硬编码演示？** 换一份首次见到且有权使用的资料，改变租户和日期，保留中间产物与逐题结果；再演示无证据和越权。固定正常问答不能证明迁移能力。

**问：20步契约证明了什么？** 它证明核心的字段、过滤、排序、引用和异常分支符合约定。真实检索质量、引用语义支持、入口认证、持久化和生产性能仍需分别验收。

**换条件自测：** 保持问题不变，只把业务日期从6月30日改成7月1日，解释为何来源从30%切到20%；再换租户，确认没有串用上一请求范围。

## 8. 本章小结与参考

- 来源、租户、版本和定位贯穿每个中间对象。
- 先过滤再排序，引用只能来自本次可见证据。
- 四段累计代码组成一个核心，HTTP与持久化通过适配器复用它。
- 契约、语义评分、认证和部署分别提供证据，不能互相代替。

第22章的评测口径落到真实请求；本章交付查证型作品，第24章再增加受控工具动作。

官方参考：[Docling](https://docling-project.github.io/docling/)。动态框架版本以实际锁文件为准。

[上一章](22-AI评测、提示注入、追踪与成本.md) · [下一章](24-ToolCalling与手写AgentLoop.md)
