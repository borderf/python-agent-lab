# 第20章　RAG、Embedding、向量库与权限过滤

[上一章](19-文档解析、字段抽取与证据定位.md) · [全书目录](教材目录.md) · [下一章](21-混合检索、重排与RAG评测.md)

## 1. 学习目标与前置知识

能为订单服务建立先取证再回答的检索链路，并保证旧版、跨租户和无证据结果不进入答案。前置：第18章的模型边界、第19章的来源与字段证据。

| 任务卡 | 内容 |
| --- | --- |
| 接收上一章产物 | 带租户、版本、有效期和定位的文档页面与字段产物 |
| 本章只新增什么 | 切块、关键词与向量检索、权限过滤、索引代次和拒答 |
| 交付什么 | 授权检索基线、真实Embedding对照或未配置说明、带引用的查询结果 |
| 怎样验收 | 当前版可见，旧版与租户外资料不进候选；无证据不调用模型 |

**本章从这里开始：** 用户问当前预付款上限，语料里同时有旧制度、新制度和另一租户制度。RAG先找有权且适用的原文，再让模型组织答案；相似度不能替代授权。

## 2. 基础知识讲解

### 2.1 RAG分开离线准备与在线查询

离线准备读取文档、切成块并保存来源元数据，再建立关键词或向量索引。在线查询先确定身份与业务日期，从可见范围中找相关块，交给模型生成带引用答案。

切块应保留标题、段落和条件，避免把“上限20%”与适用对象、例外拆开。少量重叠能缓解边界断裂，也会增加重复与成本。每块保存`chunk_id`、`source_id`、版本、租户、有效期和原文位置。

**切块大小是语义与预算的折中：**
- 字符数和token数不是同一尺度；先从标题、段落和条款等语义边界切分，再用固定题集评估大小，而不是追求统一长度。
- overlap过小可能切断条件，过大则重复证据并挤占top-k名额；重叠不能修复错误的阅读顺序或表格结构。
- 上下文预算要同时预留系统约束、问题、历史和生成空间；块变小会增加块数，块变大则可能降低单块相关性。

#### 案例推进：先跑没有模型的检索链路

固定问题“当前预付款上限是多少”，只导出候选来源与定位。确认旧版和另一租户都不在候选里，再接模型；这样检索错误不会被生成结果掩盖。

### 2.2 Embedding与向量库分工不同

Embedding模型把问题与文本转成兼容向量，余弦相似度比较方向，点积还受长度影响。查询与文档向量必须处于可比较的向量空间，并保持维度与归一化约定；同一模型是本书基线，非对称检索也可以使用分别训练但经验证兼容的查询/文档编码器。同维度的两个模型通常也不共享向量空间。

向量库保存向量与payload，并按相似度查找。近似最近邻可能漏掉正确资料，要用小语料精确结果检查召回。向量分数高只表示表示空间中接近，不证明事实、版本或权限正确。

**相似度与召回各有边界：**
- L2归一化把向量变为单位长度后，余弦相似度等于点积；点积本身受长度影响，零向量没有可靠方向，应拒绝或单独处理。
- 原始点积、余弦分数和距离不能跨模型或归一化约定直接比较；阈值也必须用当前编码器与题集校准。
- HNSW、IVF等ANN方法用近似图或粗聚类缩小搜索范围，召回受数据分布、索引参数和过滤条件影响，不保证精确top-k。
- 小语料用全量精确搜索作基线，比较ANN与精确top-k的一致性；真正的语义Recall@k还需要人工或可信标注的相关集合，不能把“与精确结果相同”当作相关性金标准。

#### 案例推进：换模型必须换索引或分开集合

把编码器从A换成B后，不能把旧向量与新问题向量混算。记录模型标签、维度、归一化、分块和来源版本，建立新索引并回归，再切换查询入口。

### 2.3 权限与版本先限制候选，再排名

服务端从可信身份得到租户，不能接受模型或用户参数任意改写。按业务日期选择生效来源，再执行检索与排序；如果先取全库top-k再过滤，别人的资料可能挤掉本应返回的证据。

有效区间采用明确端点规则，例如`valid_from <= as_of < valid_to`。历史查询按授权业务条件选择日期，不取消身份过滤。所有检索分支都使用同一可见范围，不能让模型先看到不可见材料再要求保密。

**候选前过滤要成为可执行的访问边界：**
- 把租户、权限范围和生效日期存入可过滤元数据，并用服务端身份构造条件；用户参数只能缩小范围，不能扩大范围。
- 向量库可能内部超取候选再过滤，但必须保证不可见材料不参与最终排名、上下文、引用或结果数量泄露。
- 权限服务不可用或过滤条件无法构造时应失败关闭，不能退回全库检索；撤权后的旧索引与缓存同样适用。

#### 案例推进：把越权材料放在最高分位置

手工让另一租户向量与问题完全相同，仍应在候选生成前排除。最终答案、引用、模型上下文和日志都不得出现该来源；只隐藏页面上的结果不算隔离。

### 2.4 更新、删除和无证据都是正常路径

索引是原文的派生产物。文档更新时用稳定来源ID识别同一制度，用业务版本区分内容，用索引代次区分构建产物。新代次验证完成后才切换；失败构建不能覆盖可用代次。

删除或撤权后，候选、上下文、引用和缓存都不得继续返回旧内容。缓存键至少包含租户、权限范围、问题、业务日期和知识代次。没有依据、依据冲突或只有过期版本时，明确说明缺口，不调用模型编造答案。

**让索引生命周期支持安全切换：**
- 新代次按不可变集合构建并校验块数、来源与召回，通过发布指针原子切换；全局快照模式下一次查询只读一个快照代次，避免新旧块混排。下面的概念模型按文档维护活动代次，因此不同文档可以处于不同代次。
- 重建失败时保留旧代次供回退，但回退不能恢复已撤权或已删除的内容。
- 删除先撤销在线可见性，再清理物理块、倒排项与向量；缓存按权限范围和代次失效，不能只依赖TTL。
- 后台清理异步时，可见性过滤必须同步生效；缓存删除失败要重试并告警，不能把源文件删除等同于彻底不可见。

#### 案例推进：发布指针必须包含租户

两个租户可以有同名`doc_id`。发布、可见性和删除都以`(tenant_id, doc_id)`为作用域；同代次同内容可幂等重试，同代次不同内容必须冲突。

## 3. 原理讲解与推导

### 3.1 候选范围决定检索答案的上限

排序只能重排已有候选，不能补回被过滤或截断掉的正确证据。先按身份与日期形成可见集合，再按相关性取top-k，模型才只能在正确范围内选择；先top-k后过滤则可能既越权又漏掉本租户证据。

更新索引若不切换可见代次，旧块仍会参与排名；撤权若不作用于在线过滤与缓存，删除源文件也不会真正撤下内容。因此检索正确性由“候选范围、排名、生成、引用”共同决定，不是单个相似度阈值。

## 4. 示例与逐步走查

### 4.1 第一步：用手工向量验证先过滤再评分

```python
# book-example: B20
from math import sqrt

def cosine(left, right):
    if len(left) != len(right):
        raise ValueError("vector dimensions differ")
    denominator = sqrt(sum(x*x for x in left))*sqrt(sum(y*y for y in right))
    if not denominator:
        raise ValueError("zero vector")
    return sum(x*y for x,y in zip(left,right))/denominator

rows = [{"id":"A","tenant":"a","vector":[1,0]},
        {"id":"B","tenant":"b","vector":[1,0]}]
visible = [row for row in rows if row["tenant"] == "a"]
ranked = sorted(visible, key=lambda row: cosine([1,0], row["vector"]), reverse=True)
assert [row["id"] for row in ranked] == ["A"]
```

A和B与问题的余弦分数都是1，但B不在当前租户候选内。真实检索还要检查有效期、来源身份和维度；手工向量只解释评分与过滤顺序。

### 4.2 第二步：用代次和租户作用域发布新制度

```python
# study-example: S20B
rows = []
active = {}

def publish(doc_id, generation, texts, tenant):
    key = (tenant, doc_id)
    draft = [{"doc_id": doc_id, "generation": generation, "tenant": tenant,
              "chunk": i, "text": text} for i, text in enumerate(texts)]
    if not draft or any(not row["text"].strip() for row in draft):
        raise ValueError("无效构建不能发布")
    existing = [row for row in rows if row["tenant"] == tenant
                and row["doc_id"] == doc_id and row["generation"] == generation]
    if existing:
        if [row["text"] for row in existing] != [row["text"] for row in draft]:
            raise ValueError("同代次不同内容必须冲突")
        return "unchanged"
    rows.extend(draft)
    active[key] = generation
    return "published"

def visible(tenant):
    return [row for row in rows if row["tenant"] == tenant
            and active.get((row["tenant"], row["doc_id"])) == row["generation"]]

assert publish("policy", "g1", ["上限30%"], "a") == "published"
assert publish("policy", "g2", ["上限20%"], "a") == "published"
assert [row["text"] for row in visible("a")] == ["上限20%"]
assert publish("policy", "g2", ["上限20%"], "a") == "unchanged"
try:
    publish("policy", "g2", ["上限25%"], "a")
except ValueError:
    pass
else:
    raise AssertionError("同代次不同内容应冲突")
assert publish("same", "g1", ["A租户30%"], "a") == "published"
assert publish("same", "g1", ["B租户50%"], "b") == "published"
assert publish("same", "g2", ["B租户40%"], "b") == "published"
assert [row["text"] for row in visible("a")] == ["上限20%", "A租户30%"]
assert [row["text"] for row in visible("b")] == ["B租户40%"]
try:
    publish("policy", "g3", [""], "a")
except ValueError:
    pass
else:
    raise AssertionError("空块不能发布")
assert [row["text"] for row in visible("a")] == ["上限20%", "A租户30%"]
active.pop(("a", "policy"))
assert [row["text"] for row in visible("a")] == ["A租户30%"]
assert len(rows) == 5
```

这是单进程概念模型，不是数据库并发实现。旧行逻辑隐藏后仍物理存在，真实系统必须让所有在线入口不可见；块数减少时还要删除旧尾块，并使相关缓存失效。业务版本说明制度何时生效，索引代次说明哪次构建正在使用，两者不能混为一个字段。

### 把手算向量换成真实 Embedding

**第三步：** 保持第19章来源、租户和日期过滤不变，只替换编码与索引。先用`ollama list`确认本机已有嵌入模型，再设置`EMBED_MODEL`；缺失时脚本应报错，不能把离线基线称为真实向量结果。

```powershell
if ([string]::IsNullOrWhiteSpace($env:EMBED_MODEL)) { throw "未配置EMBED_MODEL，本次没有调用真实Embedding" }
uv run --frozen python -m practice.enterprise_ai.vector_compare --embed-model $env:EMBED_MODEL
```

保存模型标签、语料版本、可见候选和关键词/向量排名。问题与文档用同一编码器，检查向量数量、有限值和非零范数；同维度不代表兼容。未启动服务或未配置模型时，结论写“真实Embedding待验”，不能声称调用成功。

## 5. 动手练习

### 本章累计任务：完成订单政策的授权检索

继续DocPilot契约第7–12步：先按租户与日期过滤，再排名、限制数量、处理空结果和稳定并列。接上真实Embedding做一次同条件对照，保存候选、模型上下文、引用和无证据案例。

**未通过时怎样定位：** 先top-k后过滤会让他人资料挤占候选；相似度不证明事实；quote存在不排除旧版或不支持结论。先检查可见集合，再检查召回、排序与生成。

**带到下一步：** 第21章用固定题集比较关键词、向量、融合和重排，判断改动究竟改善哪一层。

## 6. 验收与自测

**验收命令：** 在仓库根目录运行完整DocPilot契约；它检查权限、版本、引用位置与无证据行为，不评价真实语义质量。

```powershell
uv run --frozen python -m pytest tests/learner/contract_docpilot.py --learner-module learner_docpilot -q
```

该命令不替代第5节的真实Embedding对照记录，也不评价语义质量；未配置模型时只记录离线基线通过。

### 6.1 先预测，再查看参考推导

为什么相似度最高的旧制度不能回答“当前上限”？

<details>
<summary>完成预测后查看解释</summary>

相似度描述表示空间中的接近，不能证明时间适用性或访问权限。先按可信身份和生效日期形成候选，再排名与生成；答案只能引用实际使用的当前版本。

</details>

## 7. 面试问答与迁移

**问：相似度高为什么答案仍可能错？** 旧版、另一租户或条件相反的条款都可能高分。先校验候选资格，再评估相关性与证据支持；提高阈值不能修复授权错误。

**问：换Embedding模型后怎样维护索引？** 建立可识别的新代次，记录模型、维度、归一化与来源版本，回归后切换并准备回退。回退也必须遵守当前撤权与删除。

**问：无证据时为什么不应让模型“尽量回答”？** 没有可见依据时，任何确定答案都缺少来源。应返回证据不足、空引用和待复核状态；精确订单金额仍由确定性计算提供。

## 8. 本章小结与参考

- 离线准备与在线查询分开，切块保留条件并绑定来源定位。
- Embedding负责编码，向量库负责存储与查找，两者都必须记录兼容约定。
- 权限与日期先限制候选，再排名；越权内容不能先进入模型。
- 代次、租户作用域、删除与缓存失效共同保证旧内容不可见。
- 无证据、冲突和过期版本分别反馈，不用流畅回答填补缺口。

句子Embedding、对比学习和训练目标选读[AI基础原理册的Embedding章](../ai-foundations/03-Embedding.md)。下一章用固定题集评价检索改动。

[上一章](19-文档解析、字段抽取与证据定位.md) · [下一章](21-混合检索、重排与RAG评测.md)
