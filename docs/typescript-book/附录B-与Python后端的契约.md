# 附录B　与 Python 后端的契约

[全书目录](教材目录.md) · [附录A](附录A-面试题与参考回答.md) · [Python DocPilot 章节](../python-book/23-项目实战一：DocPilot从零到检索系统.md)

前端不复制业务规则。现有Python有两份服务：第23章的内存核心切片返回chunk；持久D2参考返回来源。调用前先选mode，不能将两种形状混合成一份网络类型。

## 已有端点与身份

两份服务均提供POST /api/search、POST /api/questions，问题使用{question, as_of}，身份由服务端凭据取得。内存核心教学身份映射a/b，D2映射tenant-a/tenant-b；正文不得覆盖身份。

| 字段/行为 | 内存核心 | 持久D2 |
| --- | --- | --- |
| 检索结果 | chunk_id/source_id/version/title/text/start/end等 | source_id/version/title/section/text等 |
| 未承诺字段 | section、score、分页游标 | chunk_id、start/end、score、分页游标 |
| 引用 | chunk_id/source_id/version/quote/start/end | source_id/version/section/quote |
| 回答外层 | answer/citations/needs_review | 另含answer_id/as_of/candidates/model/usage |

[两份冻结响应](../../typescript-examples/tests/fixtures/search-core.json)及[持久响应](../../typescript-examples/tests/fixtures/search-persistent.json)由Python真实TestClient输出核对，TS适配器读取同一份夹具。它们是契约样本，不是真实客户数据。

## 适配是运行时边界

<<< ../../typescript-examples/src/search-contract.ts

接收unknown，逐项验证后映射。UI的quote来自text；location显式区分chunk和source，不能给D2硬补0偏移，也不凭排名虚构相似度分数。返回类型不证明授权或引用支持结论；它只验证选定的传输契约。

## 错误映射

| HTTP | 业务含义 | 前端行为 |
| --- | --- | --- |
| 401 | 缺少/无效身份 | 跳登录或提示授权，不重试 |
| 403 | 无权访问该资源 | 显示无权限，不泄露资源存在性 |
| 404 | 来源/回答不存在 | 显示空状态或返回列表 |
| 422 | 请求字段不合法 | 标出字段，不重试 |
| 429 | 限流 | 按 `Retry-After` 退避 |
| 504 | 本层总等待预算到期；内存服务也映射模型TimeoutError | 保留输入，按操作、授权和预算判断 |
| 502/其他5xx | 上游失败、格式或引用错误；D2也将部分模型故障映射502 | 分类处理，不将每个5xx都自动重试 |

错误体可能是 `{"detail":"..."}`，也可能是纯文本；解析失败时保留状态码和截断文本，不要把 HTML 当 JSON。

## 流式端点（规划）

当前Python服务返回一次性JSON，真实流式端点仍需实现。第6、10章及核心工程统一使用以下事件，不在data中重复type：

```text
event: token
data: {"text":"预付款"}

event: citation
data: {"citation":{"sourceId":"policy-a","version":"2","quote":"不得超过20%"}}

event: done
data: {"answerId":"A1","needsReview":false}

```

每条事件以空行结束。error载荷为message及布尔retryable；未知事件名可忽略，已知事件坏载荷拒绝。streamAnswer只在done完成时成功；error通知界面后拒绝Promise；无终止事件的EOF也拒绝。样例本身由TS测试逐个验证。

续传需要生成开始时已取得的任务ID和服务端游标。仅在done才收到answerId、前端只知道字符数时，还没有中途续传契约。浏览器取消也不证明远端模型已停止计费。

## 偏移量的跨语言陷阱

Python 的 `start/end` 按 Unicode 码点计数，JavaScript 字符串的 `slice` 按 UTF-16 码元计数。遇到 emoji 或其他增补平面字符时，直接拿 Python 偏移去 `text.slice(start, end)` 会错位：

```ts
const text = "A😀B";
console.log(text.slice(0, 3)); // "A😀"（3 个 UTF-16 码元）
// Python 的 "A😀" 长度是 2 个码点
```

前端不要用偏移切片做高亮；把 `chunkId + quote` 作为引用标识，或由 BFF 返回已经用码点切好的片段/高亮区间。如果必须按偏移处理，先明确单位，并用同一段文本在两端做契约测试。

## 认证与密钥

- 第11章当前实现使用教学Bearer认证，由服务端authenticate映射上游凭据。第13章Cookie会话是升级任务；不能把它描述为当前已实现；
- 当前 Python 教学服务只认 `Authorization: Bearer`，BFF转发服务端确认的上游令牌；`X-Internal-Tenant` 需要 Python 明确实现并验证，不能只靠 BFF 自报；
- 模型密钥放在 BFF/服务端，前端只调用自己的受控接口；
- 令牌过期、撤权和跨租户访问要有明确错误，不能靠前端隐藏按钮；
- 日志不记录完整令牌、完整提问中的敏感内容。

## 版本与兼容

前端和后端各自发布。契约变更至少：

1. 先加兼容字段，前端可忽略；
2. 双写/灰度，观察错误与旧客户端；
3. 再切默认读路径；
4. 旧版本退出后才删字段。

类型文件应与 OpenAPI 或共享 schema 对齐；手写类型要在 CI 中做契约测试，避免两端各自漂移。

[全书目录](教材目录.md) · [附录A](附录A-面试题与参考回答.md)
