# 第23章　项目实战一：DocPilot 从零到检索系统

[上一章](22-AI评测、提示注入、追踪与成本.md) · [全书目录](教材目录.md) · [下一章](24-ToolCalling与手写AgentLoop.md)

## 1. 学习目标与前置知识

将前文组合为可演示、可评测的项目。前置：第15、18–22章。

**承接与本章主线：** 将解析、检索、生成与评测组合成用户能核对来源的项目；用正常、无证据、更新和越权案例验证完整链路。

**本章从这里开始：** 现在不再按单项技术推进，而是交付一个用户能上传文档、提问并查看证据的DocPilot。每个中间产物都必须能追溯，方便定位真实错误。

## 2. 基础知识讲解

### 2.1 将前文知识组合成一个用例

现在需要让用户真正查到制度，而非分别展示解析器、向量库和模型。综合项目把来源身份沿每一步传递：原文被解析成块，块进入候选，候选进入提示，答案再引用原文。保留中间对象，是为了在答案错误时找到最先失真的一层，而不是直接换更大的模型。

DocPilot面向有权限的文档上传、字段抽取和证据问答。先限定文档类型、用户范围、业务日期、输出字段和失败行为，不从“做一个万能知识库”开始。使用虚构材料，保留可人工核对的标准结果。

### 2.2 定义中间数据对象

Document保存来源、版本、权限和处理状态，Chunk保存文本片段和定位，Extraction保存字段与证据，Citation连接回答与来源。对象之间的标识关系应该能反向追溯，而不是只保存最终回答。

#### 案例推进：用数据对象连接端到端链路

```python
# study-example: S23A
document = {"id":"D1", "tenant":"a", "version":"v1", "text":"预付款上限20%"}
chunk = {"id":"D1:v1:0", "document_id":document["id"], "tenant":document["tenant"],
         "version":document["version"], "text":document["text"]}
question = {"tenant":"a", "text":"预付款上限？"}
visible = [chunk] if chunk["tenant"] == question["tenant"] else []
response = {"status":"evidence_found" if visible else "no_evidence",
            "source_ids":[c["id"] for c in visible]}
assert response == {"status":"evidence_found", "source_ids":["D1:v1:0"]}
```

这段只检查来源身份如何沿数据流传递，不是完整问答实现。实际项目逐步补解析、切块、检索、生成、引用和评测，每次保留输入输出。不要一开始把向量库、模型、API与界面全部接上后，才第一次检查文本有没有解析正确。

### 2.3 按可运行版本推进

版本统一采用[项目装配页的 D1–D4](../project-practice/从实验到项目交付.md#docpilot-采用同一套版本顺序)。D1 保存来源并完成可过滤的字面检索；D2 接数据库、问答接口、引用与反馈；D3 换真实模型和向量；D4 完成自己的部署、故障与用户验收。

每一版共用已经验证的身份、校验和日志边界；新增组件要给出原因，不因后续需要向量库就一开始先部署整套服务。

#### 案例推进：按四个版本交付

先按装配页从空数据库运行 D2 参考切片，沿 identity、Session、retrieve、模型适配和反馈解释一次请求。再合上参考新增一个字段，最后换陌生资料。每版使用原题回归，记录组件带来的收益、失败面和后续工作。

### 2.4 让一条查询沿全链路可观察

用户问预付款上限时，记录身份与日期、候选来源、实际进入提示的片段、最终引用和回答。如果结果错，先找错误首次出现在哪一步：解析、版本过滤、检索排序还是生成使用证据。

### 2.5 交付与项目讲述

提交启动说明、样例、固定集、故障复现与版本记录，演示当前、历史、无答案和越权四类问题。项目讲述使用实际测量与失败案例，明确哪些仍是实验和未支持文档。

#### 案例推进：演示从来源到答案，而不是只播成功聊天

展示一条正常请求的文档、块、候选、答案与引用；再展示无证据、旧版本和跨租户请求。最后制造一个已知解析错误，沿中间产物定位，修复后重跑。交付源码、锁文件、固定数据、建索引命令、评测导出与启动说明，未支持格式单独列出。

界面可以后加，先稳定服务与契约；异步文档处理需要可查询状态，而不是让浏览器无限等。索引是派生数据，更新与重建命令和版本映射也是交付的一部分。

## 3. 原理讲解与推导

### 3.1 可追溯中间产物使复杂链路可调试

单看最终文本无法判断问题来源。每次有损转换保留输入、输出标识和定位，才能逐阶段验证与替换组件。

### 3.2 版本演进应保持回归基线

新增重排等能力时保留原问题和权限约束，否则改进可能只是换了样本或绕过困难输入。用同集与新的保留集共同判断是否采用。

## 4. 示例与逐步走查

### 4.1 从空文件写出第一条可验证链路

前面分别学习模型、资料、检索和评测，现在不再跳到完整参考服务。新建 `learner_docpilot.py`，用四个函数串起同一条数据流：规范化→索引→检索→证据回答。首次采用等长文本块和字符二元组检索，让行为可手算；它们是基线，不冒充语义检索。

```mermaid
flowchart LR
    A[原始资料] --> B[规范化与区间]
    B --> C[有偏移的稳定片段]
    C --> D[先租户日期过滤]
    D --> E[排序与截断]
    E --> F[本次证据]
    F --> G[模型候选]
    G --> H[结构与引用检查]
```

先按下面每步的契约自己实现，再对照每组累计代码找首个分叉。四组代码依次写在同一个文件，后组调用前组函数，不能当作四个互不相关的示例。这里的导入均来自标准库，不需要模型账户或向量服务。

每完成一步，运行下列命令，把最后的1改成当前步骤号：

```powershell
uv run --frozen python -m pytest tests/learner/contract_docpilot.py --learner-module learner_docpilot --through-step 1 -q
```

较后步骤显示 deselected，前面步骤继续回归。用参考模块运行只能证明基线，自己的结果保留实际模块名。[完整契约与失败定位](../../tests/learner/练习说明.md)

### 4.2 步骤1–6：让资料先成为可靠输入

**步骤1，建立来源模型。** 输入必须恰好包含 source_id、tenant_id、version、title、text、valid_from、valid_to。前五项是非空文本，返回新字典，输入不变。为什么先做这个？若来源或租户缺失，后面再正确排序也无法解释答案属于谁。先用首尾空白和空文本验证。

**步骤2，明确生效区间。** 日期用 YYYY-MM-DD，valid_to 可空且必须晚于 valid_from。把区间定义为左闭右开，7月1日切换时旧版不再有效。日期规范化后才能按相同格式比较文本；不能拿任意日期字符串排序。下面是前两步的累计实现。

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

**步骤3，建立片段身份。** 先一份文档一个块，让 source_id、tenant_id、version 和 chunk_id 跟随正文。不要只保存一段文本，否则后面无法回到特定版本。

**步骤4，保存定位。** 将“甲乙丙丁戊己庚”每3个码点切一块，得到甲乙丙、丁戊己、庚。每块记录 start、end，必须等于规范化全文的该切片。这里不是UTF-8字节偏移，也不是PDF页码；转换到PDF时另建定位。

**步骤5，保证稳定与隔离。** 相同输入再次索引应得到相同ID；同一来源的不同位置不能冲突；不能修改输入。将长度设为0或True必须拒绝，因为True虽然可参与整数运算，却不是本接口允许的长度。

**步骤6，区分重复和冲突。** 同租户、同来源、同版本的相同内容只建一次；不同内容报错，不能覆盖成“最新”。不同租户允许同名来源。这里的索引是一次构建；真实增量入库还要实现持久唯一键和更新事务。

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

先运行到第6步，检查片段原文与偏移，再继续。等长分块会切断语义；本阶段先暴露这一限制，第20–21章再基于失败样本比较分块和召回策略。

### 4.3 步骤7–12：先限制范围，再讨论相关性

**步骤7，先按可信租户过滤。** 核心函数接收服务端已经确定的 tenant_id，只让该范围进入排名。测试把其他租户资料放在前面，再取 top1；如果先截断再过滤，就会漏掉本租户结果。核心过滤通过还不证明HTTP入口认证正确。

**步骤8，过滤适用日期。** 旧版适用到7月1日前，新版从7月1日起。用6月30日与7月1日的相同问题检验；仅改一个条件，才能定位日期边界。

**步骤9，建立可手算分数。** “预付款”二元组是“预付”“付款”。与标题和正文生成的词项集合求交集并计数。共有两项比只有“付款”的一项排前；这不是embedding，不具备可靠同义理解。

**步骤10，限制候选预算。** limit只接受1–10的整数，排除bool。先得到合法范围的排名，再截断。预算既影响费用也影响召回，不能让客户端任意放大。

**步骤11，允许空结果。** 与“天气晴朗”没有公共词项时返回空，不为凑满top-k加入无关材料。无依据是合法业务结果；网络或模型异常则是另一类失败。

**步骤12，消除并列与共享的不确定性。** 同分按来源、版本和起点排序，输入顺序反转仍一致。返回独立数据，调用者修改结果不能改坏索引。至此使用第1章名称与对象、第3章复制知识保护跨请求状态。

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

运行到第12步，手画“过滤前→过滤后→排名→截断”。如果结果不对，先找资料是否曾进入候选，不要马上更换模型。

### 4.4 步骤13–20：让模型成为受检验的候选来源

**步骤13，只把本次可见证据送给模型。** 定义回调 `model(question, evidence)`，先用替身逐字返回第一个片段与chunk_id。模型协议与业务函数分开，之后可以替换实际调用适配器。

**步骤14，无证据不调用模型。** 此时程序直接返回说明、空引用和needs_review=True。测试中的模型回调一旦被调用就报错，证明拒答来自程序路径，而不是寄希望于提示。

**步骤15，检查候选结构。** 只接受answer、citations、needs_review；文本非空，复核标记必须是真正bool。字符串“false”不能按真假转换，否则非空字符串反而为真。额外tenant_id一律拒绝。

**步骤16，引用只能来自本次证据。** 不能仅到全库查询某个ID存在就接受；它可能属于其他租户、其他日期或未送入模型的资料。

**步骤17，逐字核对引用。** quote必须在指定片段中，空白引用拒绝。它证明位置，不证明支持结论：“上限20%”配回答“允许80%”仍应被人工语义评分判错。

**步骤18，处理重复与缺依据。** 相同引用不得重复，无引用不能标为无需复核。允许有引用却仍需复核，因为资料可能不足以完成整个任务。

**步骤19，保存可信依据并暴露故障。** 模型回调得到证据副本，校验使用另一份可信快照。回调超时继续抛给服务层，不能悄悄换替身或返回“没找到”。真实适配器还要记录实际模型、用量与结束原因。

**步骤20，交替上下文做整体验收。** 在同一个索引上依次查A历史、B当前、A当前与无资料租户，结果分别来自30%、80%、20%与无证据。这检查组合后没有残留上一请求的范围。最后换一组金额和生效日期重做。

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

以上累计代码是一种可读基线，不要求你的内部实现相同。20项契约通过证明已覆盖行为；它们没有证明真实语义检索、引用支持结论、入口认证或生产性能。

### 4.5 将同一个核心接到HTTP，而不是重写业务

先完成自己的核心，再设置模块名：

```powershell
uv sync --frozen --group web --inexact
$env:LEARNER_MODULE = 'learner_docpilot'
uv run --frozen --group web uvicorn practice.learning_projects.service:create_app --factory --host 127.0.0.1 --port 8011
```

打开 `http://127.0.0.1:8011/docs`，使用教学令牌demo-a或demo-b授权。向 `/api/questions` 发送 question“预付款”和as_of“2026-07-01”，换历史日期与另一令牌核对结果。请求体不允许自报tenant_id。该切片明确使用内存索引和替身，重启重建，不是完整登录或持久系统。

[HTTP适配器](../../practice/learning_projects/service.py)只处理请求模型、可信教学身份和错误映射：超时返回504，坏模型输出返回502，无证据是正常复核结果。业务核心继续使用你的四个函数。把一个边界换成真实模型时，重新验同一组行为，不将模式切换隐藏在默认回退中。

完成契约后，用[逐题评测入口](../../tests/learner/练习说明.md#从契约检查继续做逐题评测)对自己的模块导出开发题与留出题，保留失败，不把替身结果当真实质量。随后按[项目装配](../project-practice/从实验到项目交付.md)接持久资料、PDF、真实模型、向量、反馈与部署。保留每层中间结果；这部分是20步核心之外的产品交付，不因核心全绿而自动完成。

### 4.6 把内存核心迁移到持久化服务

20步的核心把资料放在内存列表里；项目装配手册的D2参考切片从数据库读取。两者不是两套业务，而是同一组函数的两种资料来源。迁移时保留自己的四个函数，只替换“资料从哪里来、把哪些字段存下去”。

| 类别 | 内容 | 迁移要求 |
| --- | --- | --- |
| 保留 | `normalize_document`、`build_index`、`search`、`answer` 的输入输出契约 | 不改函数签名；原有20条契约继续通过 |
| 新增 | 文档仓储：`load_all()` 返回与内存版相同的文档字典；`save(document)` 持久化来源 | 仓储只做字段映射，不复制校验规则 |
| 转换 | 数据库列 → 文档字典；文档片段 → `chunk_id/start/end`；回答 → 持久记录 | 映射表写进代码注释，空值按业务规则处理 |
| 替换 | 启动时用仓储取资料调用 `build_index`；上传成功后先保存再重建索引 | 不在请求里重建全量索引 |

迁移顺序：

1. 先让仓储返回与内存样例完全相同的文档字典，跑原有20条契约，确认业务没有改变。
2. 把服务启动时的 `documents` 换成仓储读取结果；重启后重新调用 `build_index`，确认同一问题仍返回同一来源和版本。
3. 上传入口改为“校验 → 保存 → 重建索引 → 返回来源 ID”；保存失败时不返回成功，旧索引仍可用。
4. 增加一条独立验收：写入一份资料，停止服务，重新启动，再问同一问题；候选、引用和版本都应保留。
5. 最后才换真实模型、向量和部署；每次只换一层，保留旧题回归。

这一步的完成证据是自己的仓储实现和重启后的查询记录，不是“参考切片能启动”。参考切片只用来对照字段和错误映射；自己的四个函数仍是业务核心。[项目装配](../project-practice/从实验到项目交付.md#docpilot-采用同一套版本顺序) · [契约](附录E-项目里程碑与交付检查.md)

## 5. 动手练习

### 本章累计任务：从空文件累计完成DocPilot

按本章20步写自己的模块，用明确模块名验收，再用一份新资料与另一组日期重做。最后接同一核心到HTTP与用户来源页。

**未通过时怎样定位：** 参考基线通过不是自己的完成证据；20步核心不含完整生产功能；语义评分、认证与部署分别补证据。

**带到下一步：** 若任务只需查证，可以在此交付；需要动作时进入第24章。

下方专题练习用于补当前卡点；先完成这一项累计任务，不另将所有索引作为必须并行完成的进度。


### 从核心到产品的一次独立交付

换一份首次见到且有权使用的材料，完成规范化、索引、提问与原文核对；再用无相关条款的材料重做。接HTTP后分别检查正常、无证据、坏输入与未知身份；后续真实模型、持久化和部署按装配手册逐项补证据。

用[评测方法](../project-practice/评测与故障演练.md)准备开发题与未参与调参的题，人工标注引用是否支持结论。请另一人独立完成陌生查证任务，记录求助、错误、总耗时与一次修复；没有真实观察时写尚未验证。

交付只需一页索引：自己的模块与20步命令、服务入口、数据与模型版本、逐题结果、失败修复和已知限制。任务只需查证时在此交付；需要动作再进入第24章。

## 6. 验收与自测

**知识生命周期验收：** 接入第20章的发布与可见性设计，演练构建失败、制度升级、删除与撤权，检查候选、上下文和缓存；接入第22章逐题记录，坏输出、超时与无证据均不能被跳过。语义正确性由人工标注/核对补充，不用Schema通过代替。

**行为验收：** 新环境可复现；引用正确；权限不越界；模型/数据版本可定位；记录已知限制。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

### 6.1 先预测，再查看参考推导

若最终答案错了，首先应该换更大模型吗？

<details>
<summary>完成预测后查看解释</summary>

先沿解析、权限过滤、召回、排序、上下文和生成定位，判断证据在哪一步丢失或误用。模型变化只适合解决有证据支持的对应瓶颈，且要经过固定集对照。

</details>

## 7. 面试问答与迁移

用五分钟讲清DocPilot架构、一个失败案例及一次实际改进，展示前后指标而非泛泛“效果提升”。

## 8. 本章小结与参考

### 8.1 主要知识点总结

- DocPilot将资料导入、定位、授权检索、引用回答和反馈连成一条用户路径。
- 按D1–D4逐步替换实现，数据契约与旧行为检查随版本累计。
- 真实模型、向量与部署分别验证，离线替身帮助先定位工程错误。
- 可交付成果包括运行说明、评测、失败修复、独立使用与范围说明。

### 8.2 日常工作注意事项

- 新增来源字段时同步考虑输入模型、数据库迁移、返回结构、界面和旧数据，避免只在本机手工改表。
- 打开引用时再次检查访问范围；资料查询、回答和反馈都按同一可信主体关联。
- 试用者提出新问题后先找首个出错层，再改一项并跑旧题；不要靠替换几条展示答案掩盖链路问题。

### 8.3 参考与后续学习

到这里已有完整AI应用作品。继续动作与Agent学习进入第24章；若当前目标是知识问答交付，可先用[第29章](29-原理面试：语言、工程与AI的追问.md)及[第30章](30-转行准备、项目讲述与系统设计面试.md)获取反馈。

DocPilot汇合文档、权限、检索、生成与评测。下一个项目在证据基础上增加工具决策、持久任务与审批动作。

官方参考：[本章资料](https://docling-project.github.io/docling/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](22-AI评测、提示注入、追踪与成本.md) · [下一章](24-ToolCalling与手写AgentLoop.md)
