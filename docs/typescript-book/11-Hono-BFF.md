# 第11章　Hono BFF：路由、中间件与错误边界

[上一章](10-流式AI界面.md) · [全书目录](教材目录.md) · [下一章](12-SQL与Drizzle事务.md)

## 1. 学习目标与前置知识

能搭一个 Hono BFF：请求 ID、认证中间件、输入校验、上游转发、超时/取消、统一错误映射和 SSE 透传；能说清哪些逻辑属于 BFF，哪些必须留在 Python 业务服务。前置：第 5–7、10 章；熟悉 Spring MVC 的 Controller/Filter/Advice 更佳。

**本章从这里开始：** 浏览器直接调 Python 服务，会把模型密钥、内部地址和租户参数暴露出去；每个前端各自做认证和错误映射，也会产生多套规则。BFF（Backend for Frontend）不是“再加一层转发”，而是**信任边界和契约适配层**。

## 2. 基础知识讲解

### 2.1 BFF 的职责边界

BFF 负责：

- 终止浏览器会话/令牌，映射为可信身份；
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

### 2.7 SSE透传是后续明确的集成任务

当前createBff实现/api/search；当前Python服务也没有/api/chat/stream。先运行第6章的受控流测试，再增加真实流式上游。透传需先验证状态和text/event-stream，直接交付upstream.body，并处理客户端断开、截止时间、代理缓冲与流结束指标。

不能先response.text()再声称流式；不能强行把任何上游JSON标成event-stream。SSE透传、真实Cookie会话和上游模型取消要分别留下集成证据，不由搜索测试通过推断。

## 3. 原理讲解与推导

### 3.1 BFF 是信任边界，不是业务层

浏览器不可信：它可以伪造 `tenant_id`、改金额、跳过按钮。BFF 的每个受保护路由都必须从**已验证凭据**得到身份，再决定上游能访问什么。上游服务也要再校验一次，不能只信 BFF 的 header；纵深防御。

### 3.2 错误映射要稳定

前端不应解析 Python 的异常文本。BFF 把上游错误归类为 `unauthorized/forbidden/not_found/invalid_input/upstream_timeout/upstream_error`，前端按 code 分支。上游新增错误时，BFF 映射表要更新并测试。

### 3.3 超时是预算，不是单个数字

一次请求可能经过浏览器 → BFF → Python → 模型。每层都要有超时，且总预算递减；各层应共享截止时间并为返回留余量。例如浏览器15秒、BFF14秒、内部工作13秒是规划示意，不是三个彼此独立的保证；上游工作必须在外层截止前留出返回时间。超时后要取消耗时工作，而不是只返回 504。

## 4. 示例与逐步走查

以下是实际通过Hono app.request集成检查的应用工厂：

<<< ../../typescript-examples/src/bff.ts

authenticate、上游地址、响应模式和fetch边界可注入，测试只替换上游，不替换认证与请求/响应校验。mode明确选择Python内存核心或持久D2，两份字段不能混成一张类型表。

[search-contract.ts](../../typescript-examples/src/search-contract.ts)负责把snake_case转换为界面模型，缺字段报502，不用as跳过。测试同时检查无身份拒绝、合法身份成功、伪造租户、非法日期、上游状态、超时及响应字段。

## 5. 练习

### 练习一：跟写

给 `/api/search` 增加总超时 10 秒；客户端断开或超时都中止上游，返回 `504`/`499`，并记录耗时。

### 练习二：改造

把认证从 Bearer 改成 HttpOnly Cookie 会话；说明 CSRF 风险、SameSite 设置和登出时如何让会话失效。

### 练习三：独立

实现 `/api/chat/stream` 的透传，要求：非 2xx 不开始流；上游断开时结束响应；不缓冲、不压缩；客户端 abort 后上游也取消。用假上游写一个契约测试。

## 6. 验收与自测

**行为验收：** 搜索路径的无身份401、合法请求200、伪造租户422、预算超时504与取消区分均由集成测试检查。真实连接断开传播、Cookie会话与SSE透传属于后续任务，完成后另补运行记录。

**原理验收：** 能解释 BFF 与业务服务的职责边界、信任边界、超时预算和错误映射；能说出为什么不能只信前端传的租户。

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

- BFF 是信任边界和契约适配层，不复制业务规则。
- 身份来自可信凭据；前端自报 tenant 一律拒绝。
- 统一错误形状和 requestId；上游错误映射成稳定 code。
- 超时/取消/SSE 透传要贯穿到上游。

参考：[Hono](https://hono.dev/docs/)、[MDN Fetch](https://developer.mozilla.org/docs/Web/API/Fetch_API)、[SSE](https://developer.mozilla.org/docs/Web/API/Server-sent_events)。

[上一章](10-流式AI界面.md) · [全书目录](教材目录.md) · [下一章](12-SQL与Drizzle事务.md)
