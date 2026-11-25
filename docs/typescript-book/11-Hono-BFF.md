# 第11章　Hono BFF：路由、中间件与错误边界

[上一章](10-流式AI界面.md) · [全书目录](教材目录.md) · [下一章](12-SQL与Drizzle事务.md)

## 1. 学习目标与前置知识

能搭一个 Hono BFF：请求 ID、认证中间件、输入校验、上游转发、超时/取消、统一错误映射和 SSE 透传；能说清哪些逻辑属于 BFF，哪些必须留在 Python 业务服务。前置：第 5–7、10 章；熟悉 Spring MVC 的 Controller/Filter/Advice 更佳。

**本章从这里开始：** 浏览器与Python业务服务之间可以增加一个专门服务页面的后端，叫BFF（Backend for Frontend）。它检查浏览器会话，把请求转换为内部接口需要的格式，并保管模型密钥等服务端信息。Python服务仍需检查业务权限；增加BFF的目的是明确这些分工，接下来沿一次搜索请求逐步实现。

## 2. 基础知识讲解

### 2.1 BFF 的职责边界

BFF 负责：

- 验证浏览器带来的会话或令牌，确认用户身份；
- 校验请求形状，拒绝前端自报 `tenant_id`；
- 转发到内部服务，附上可信身份；
- 把上游错误映射成稳定错误码；
- 处理超时、取消、流式透传；
- 记录请求 ID、耗时、状态，不记录敏感正文。

BFF 不负责：检索算法、引用支持结论、审批规则、模型提示词版本。这些仍在 Python 服务；BFF 只做边界，不复制业务。

### 2.2 最小 Hono 应用

```ts
import { Hono } from "hono";

type AppEnv = {
  Variables: {
    requestId: string;
    tenantId: string;
    upstreamToken: string;
  };
};

const app = new Hono<AppEnv>();

app.get("/health", (c) => c.json({ ok: true }));

app.use("*", async (c, next) => {
  const requestId = crypto.randomUUID();
  c.set("requestId", requestId);
  c.header("X-Request-Id", requestId);
  await next();
});

export default app;
```

`Hono<AppEnv>` 的 `Variables` 是中间件写入、后续处理器读取的类型化上下文。Java 的 `request.setAttribute` 没有类型约束；这里用泛型把 `tenantId`/`requestId` 的键固定下来。

Node 启动：

```ts
import { serve } from "@hono/node-server";
import app from "./app.js";

serve({ fetch: app.fetch, port: 8787 });
```

`@hono/node-server` 是独立的包，不在配套工程 `typescript-examples` 的锁文件内，运行前需自行安装；配套工程改用 Node 原生 `node:http` 挂载同一个 Hono 应用（见 `typescript-examples/src/server.ts`），两种方式选一种即可，不要混用端口与生命周期。

### 2.3 身份与中间件顺序

本章先用Bearer建立教学边界。authenticate由服务端注入，将有效凭据映射为Actor及允许转发的upstreamToken；不能由请求体取得租户。第13章再把浏览器凭据换成Cookie会话，但继续复用搜索与转发规则。

请求ID先于认证，401也有可追踪ID。实际构建AppEnv、认证中间件和错误映射都在第4部分的createBff中，不需要把本章不同阶段的app声明拼成一个文件。

### 2.4 校验请求与实际日期

parseSearchBody只接受question/as_of，按Unicode码点限制2–1000字符，拒绝不存在的日期。正则只能证明日期格式，不能证明2月30日存在。校验器与转发函数放在同一个transport模块，在下一节展示。

### 2.5 稳定错误与取消来源

客户端已取消时抛RequestCancelled；只有本层deadline到期才产生504，其他网络/格式故障映射502。上游明确返回的401/403/404/422/429保留可识别语义。不要仅凭异常叫AbortError就认定预算超时。

本地测试可用499标记取消；真实客户端已经断开时通常无法再给它发送响应。用户错误体包含稳定code与requestId，不回传堆栈或上游凭据。

### 2.6 统一校验、转发与总等待时限

<<< ../../typescript-examples/src/transport.ts

定时器覆盖收到响应头与读取JSON的整个过程，finally清理。取消来源来自各自signal的状态，而非异常名称；测试分别注入客户端取消、预算到期和普通网络错误。传入的底层fetch仍需响应signal，这不是任意代码的强制终止器。

### 2.7 SSE透传与当前模型演示的边界

当前 `createBff` 实现 `/api/search`，另有独立 `/api/answer`：它把 Ollama NDJSON 映射为应用 SSE（第6章），不是通用上游 SSE 透传，也不包含 RAG。Python 检索服务当前仍返回一次性 JSON。

通用透传仍需先验证状态和 `text/event-stream`，直接交付 `upstream.body`，并处理客户端断开、截止时间、代理缓冲与流结束指标。不能先 `response.text()` 再声称流式，也不能强行把任意上游 JSON 标成 `event-stream`。真实 Cookie 会话与供应商取消要分别留下集成证据，不能由搜索或假上游测试推断。

### 2.8 搜索请求：从浏览器输入到BFF输出

当前 `/api/search` 的完整契约如下。请求体只允许两个字段，`tenant_id`不是“可选的租户参数”，多出来就拒绝。

```text
POST /api/search
Authorization: Bearer demo
Content-Type: application/json

{"question":"预付款","as_of":"2026-01-01"}
```

认证通过后，BFF把浏览器token换成Actor中的upstreamToken，再把规范化的question/as_of转发到`${upstreamUrl}/api/search`。前端不能直接看到或填写这个上游token。core模式收到Python的snake_case响应后，输出camelCase：

```text
HTTP 200
X-Request-ID: <uuid>
Content-Type: application/json

{"items":[{"sourceId":"policy-a","version":"1","title":"付款制度",
"quote":"预付款20%。","location":{"kind":"chunk","chunkId":"chunk-1","start":0,"end":7}}]}
```

这里`end=7`必须等于引文的Unicode码点数；persistent模式输出`location.kind="source"`和section。两种location由创建BFF时的mode选择，不能从同一份字段里猜。缺title、quote或偏移都会变成502 `invalid_response`，不是补默认值。

### 2.9 错误映射表：先区分发生在哪一层

| 发生位置/原因 | HTTP或流内结果 | 稳定code/字段 | 是否继续调用上游 |
| --- | --- | --- | --- |
| 缺少或无效Bearer | 401 | `unauthorized` | 否 |
| 坏JSON | 422 | `invalid_json` | 否 |
| 多tenant_id、坏日期、问题长度越界 | 422 | `invalid_input` | 否 |
| 上游返回401/403/404/422/429 | 保留该状态 | `upstream_401`等 | 已返回，取消body |
| 上游其他非2xx | 502 | `upstream_502` | 已返回，取消body |
| 连接失败或JSON读取失败 | 502 | `upstream_failure` | 否/已中断 |
| BFF预算到期 | 504 | `upstream_timeout` | signal取消上游 |
| Python字段不符合mode | 502 | `invalid_response` | 已结束 |
| `/api/answer`未配置模型 | 503 | `model_unconfigured` | 否 |
| 流已200开始后供应商失败 | HTTP仍200，SSE error | message/retryable | 已取消reader |
| 客户端取消 | 本地分类499；真实断开通常无法送达 | 无用户错误体 | 取消上游 |

普通错误体固定为`{"error":{"code":"...","message":"...","requestId":"..."}}`。前端按code和status分支，不解析上游异常文本；requestId用于把用户报告关联到服务端日志。

### 2.10 `/api/answer`的输入、输出与调用边界

该端点只接受`{"question":"预付款"}`，问题trim后按码点计2–1000字符。BFF把Ollama `/api/chat`的NDJSON逐行映射成应用SSE：text变token，tool_calls变tool，正常stop变done，length/unknown/断流变error。done的answerId使用BFF requestId，needsReview固定true；它没有RAG引用。

```text
成功事件顺序：event: token … →（可选event: tool …）→ event: done …
失败事件顺序：event: token … → event: error … → 关闭响应
```

**重要边界：** 第10章`AnswerPage`默认发送`{question, as_of}`，比当前端点允许的字段多一个as_of；直接接入会得到422 `invalid_input`。接到当前 `/api/answer` 时应只发送`{question}`，像`host-client.tsx`那样；若要保留业务日期，必须先明确扩展服务端协议。不能把第10章组件直接接到本端点后声称已经兼容。

## 3. 原理讲解与推导

### 3.1 BFF 是信任边界，不是业务层

浏览器不可信：它可以伪造 `tenant_id`、改金额、跳过按钮。BFF 的每个受保护路由都必须从**已验证凭据**得到身份，再决定上游能访问什么。上游服务也要再校验一次，不能只信 BFF 的 header；纵深防御。

### 3.2 错误映射要稳定

前端不应解析 Python 的异常文本。BFF 的稳定 code 见 2.9 表：入口层 `unauthorized/invalid_json/invalid_input`，上游状态 `upstream_401/upstream_403/upstream_404/upstream_422/upstream_429/upstream_502`，连接或响应不合法 `upstream_failure`，预算到期 `upstream_timeout`，字段不合 mode `invalid_response`。前端按 code 和 status 分支；上游新增错误时，映射表要更新并测试。

### 3.3 超时是预算，不是单个数字

一次请求可能经过浏览器 → BFF → Python → 模型。每层都要有超时，且总预算递减；各层应共享截止时间并为返回留余量。例如浏览器15秒、BFF14秒、内部工作13秒是规划示意，不是三个彼此独立的保证；上游工作必须在外层截止前留出返回时间。超时后要取消耗时工作，而不是只返回 504。

### 3.4 当前计时与取消究竟覆盖到哪

`forwardSearch`在调用fetch前创建deadline，`AbortSignal.any([clientSignal, deadline.signal])`同时监听浏览器取消和预算到期。定时器一直保留到`response.json()`完成，因此不只覆盖响应头；但认证查询、Hono读取/校验JSON发生在forwardSearch之前，不在这段计时内。若把“15秒”理解成完整端到端保证，就会漏掉这些前置耗时。

`streamOllama`的deadline覆盖从调用供应商到NDJSON流结束；`/api/answer`把客户端signal与流cancel signal合并。Node入口在请求aborted或响应close且未正常结束时abort，pipeline再把下游取消传回Response.body。这里取消的是本地fetch/reader；不能据此断言供应商已停止推理或计费。

| 信号来源 | 识别方式 | 搜索路径结果 | 流路径结果 |
| --- | --- | --- | --- |
| 浏览器/Node入口断开 | `clientSignal.aborted` | RequestCancelled，本地映射499 | 停止写入并关闭，通常无法再发HTTP错误 |
| BFF deadline | `deadline.signal.aborted`且客户端未取消 | 504 `upstream_timeout` | SSE error，retryable=true |
| 上游主动AbortError | 两个signal都未abort | 502 `upstream_failure` | 视具体错误映射，不能误报504 |
| 正常done/error | 协议终止事件 | 不适用 | 终止读取并取消剩余reader |

catch中先判断客户端、再判断deadline，是因为一次取消可能同时触发两者；顺序决定错误分类。HTTP头一旦以200发出，后续超时只能通过SSE error表达，不能把状态改成504。

## 4. 示例与逐步走查

以下是实际通过Hono app.request集成检查的应用工厂：

<<< ../../typescript-examples/src/bff.ts

authenticate、上游地址、响应模式和fetch边界可注入，测试只替换上游，不替换认证与请求/响应校验。mode明确选择Python内存核心或持久D2，两份字段不能混成一张类型表。

[search-contract.ts](../../typescript-examples/src/search-contract.ts)负责把snake_case转换为界面模型，缺字段报502，不用as跳过。测试同时检查无身份拒绝、合法身份成功、伪造租户、非法日期、上游状态、超时及响应字段。

### 4.1 沿请求记录逐段核对

| 阶段 | 输入 | 预期输出/副作用 | 应保留的证据 |
| --- | --- | --- | --- |
| requestId中间件 | 任意请求 | 响应头X-Request-ID，后续错误体也带它 | 401响应中的requestId |
| authenticate | Authorization头 | Actor或null；不读取body.tenantId | 无身份时上游fetcher调用数为0 |
| parseSearchBody | unknown JSON | `{question, as_of}`或422 | 2026-02-30与额外tenant_id均拒绝 |
| forwardSearch | Actor.upstreamToken、signal | Python JSON或分类失败 | 上游收到服务端token，body不含tenant_id |
| parseSearchResponse | unknown、mode | `{items: SearchHit[]}`或502 | 删除text/offset后失败 |
| SSE映射 | Ollama NDJSON | token/tool/done或error | 提前EOF不发done；客户端取消不继续enqueue |

这张表也是排障顺序：先看有没有requestId，再看认证/校验是否阻止转发，然后看上游状态，最后看映射。不要一遇到500就改模型提示词。

## 5. 练习

### 练习一：跟写

`timeoutMs`已经注入`createBff`，不要重复实现一套定时器。先读`forwardSearch`，把测试预算改为10秒并用可控时钟/假上游验证：客户端断开与预算到期分别分类，读取body超时也中止。再说明为什么认证和JSON解析时间不在当前deadline内；若要覆盖完整请求，应把计时边界移到中间件入口并保留返回余量。

### 练习二：改造

把认证从 Bearer 改成 HttpOnly Cookie 会话；说明 CSRF 风险、SameSite 设置和登出时如何让会话失效。

### 练习三：独立

实现 `/api/chat/stream` 的透传，要求：非 2xx 不开始流；上游断开时结束响应；不缓冲、不压缩；客户端 abort 后上游也取消。用假上游写一个契约测试。

## 6. 验收与自测

**行为验收：** 搜索路径的无身份401、合法请求200、伪造租户422、预算超时504与取消区分均由集成测试检查；本地真实HTTP的下游取消也有`real-http-stream.test.mjs`证据。供应商停止生成/计费、Cookie会话与通用SSE透传仍是后续边界，不能由本地取消测试推断。

**原理验收：** 能解释 BFF 与业务服务的职责边界、信任边界、超时预算和错误映射；能说出为什么不能只信前端传的租户。

| 操作 | 预期 | 证据位置/断言 |
| --- | --- | --- |
| 不带Authorization调用`/api/search` | 401 unauthorized，带requestId | `integration.test.mjs`无身份用例 |
| 带合法身份和合法body | 200，上游收到server-token，输出camelCase | 合法搜索用例检查init.headers/body |
| body加入tenant_id或2026-02-30 | 422 invalid_input，不调用上游 | 伪造租户/坏日期用例 |
| 假上游等待abort，预算5ms | 504 upstream_timeout | 总时限用例 |
| 客户端先abort，上游也等待同一signal | RequestCancelled，不误判504 | 客户端取消与预算分开用例 |
| 删除Python夹具text或改错偏移 | 502 invalid_response/解析失败 | 两份夹具适配与坏location用例 |
| `/api/answer`提前EOF或length | HTTP200内出现error，不出现done | `answer-stream.test.mjs`结束原因用例 |
| 本地HTTP客户端取消reader | BFF取消上游连接，不继续写 | `real-http-stream.test.mjs`下游停止读取用例 |

表中是现有断言的定位，不是本次编辑重新运行测试的结论。新增供应商取消、公网链路或Cookie会话必须保留各自运行记录。

### 6.1 先预测，再查看解释

BFF 已经校验了 `tenant_id`，为什么 Python 服务还要再校验一次？

<details>
<summary>完成预测后查看解释</summary>

BFF 可能被绕过、配置错误或被攻破；内部服务也可能被其他调用方直接访问。纵深防御要求每个边界都从可信凭据重新确认身份和权限，不能把“上游已校验”当成授权。

</details>

## 7. 面试问答与参考回答

**问：BFF 和 API Gateway 有什么区别？**

Gateway 偏通用流量治理（路由、限流、TLS），BFF 偏某一客户端的契约适配（会话、字段裁剪、SSE、错误形状）。小项目可以合并，但职责要分清。

**问：为什么浏览器不能直接拿模型密钥？**

浏览器代码和网络请求对用户可见，任何打包进前端的密钥都可被提取。密钥只能放服务端，由 BFF/后端代理调用，并做身份、配额和审计。

**问：SSE 透传为什么不能先读完整 body？**

`response.text()` 会等整个流结束，失去增量；必须把 `upstream.body` 作为 `Response` 的流直接返回，并确保中间层不压缩/缓冲。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 浏览器与内部 Python 服务之间，BFF 该承担哪些边界职责，又不能复制哪些业务？

**一条主线：**

```text
浏览器请求
→ 认证/校验/转发/错误映射/超时预算
→ 稳定错误码、requestId 或 SSE 流
```

**三个关键词：** 信任边界、可信身份、稳定错误码。身份来自凭据，字段经过运行时校验，错误按来源映射；流开始后错误改走SSE。

**最容易错：**
- 从body/前端header取租户；把mode两种响应当成同一契约。
- 把上游AbortError当成本层超时；只取消本地Promise不取消fetch/reader。
- 认为deadline覆盖认证和解析；流头200后还想改写HTTP状态。
- 把Ollama协议演示当RAG/通用SSE透传，或忽略`AnswerPage`双字段与当前端点的差异。

**与前后章：** 第10章定义前端事件与终态；第12章的持久化承接BFF校验后的可信身份和业务键。

**学完应能：** 按一次请求列出输入、输出、调用边界和401/422/502/504证据；区分搜索JSON、模型SSE、通用透传三种尚未相同的协议。

### 8.2 参考与后续学习

参考：[Hono](https://hono.dev/docs/)、[MDN Fetch](https://developer.mozilla.org/docs/Web/API/Fetch_API)、[SSE](https://developer.mozilla.org/docs/Web/API/Server-sent_events)。

[上一章](10-流式AI界面.md) · [全书目录](教材目录.md) · [下一章](12-SQL与Drizzle事务.md)
