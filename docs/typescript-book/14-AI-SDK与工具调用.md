# 第14章　AI SDK、工具调用与 MCP

[上一章](13-认证多租户与权限.md) · [全书目录](教材目录.md) · [下一章](15-Vitest与契约测试.md)

## 1. 学习目标与前置知识

能在 BFF 里接模型 SDK/HTTP，处理流式文本、工具调用、结构化输出和用量；能给工具加参数校验、允许列表、租户边界与人工审批；能判断什么时候用 MCP、什么时候直接调用。前置：第 5–6、11–13 章。

**本章从这里开始：** 模型说“请调用导出工具”，前端就把用户数据导出；模型返回一段 JSON，代码直接 `as Report`；工具参数是用户输入，却直接拼进 SQL。模型输出是**不可信输入**，工具调用是**有权限的副作用**，两者都必须经过服务端校验。

## 2. 基础知识讲解

### 2.1 先抽象模型边界，再选 SDK

不同供应商的 SDK 名字不同，但边界相似：

```ts
type ModelEvent =
  | { type: "text-delta"; text: string }
  | { type: "tool-call"; callId: string; name: string; arguments: unknown }
  | { type: "finish"; usage: { inputTokens: number; outputTokens: number } }
  | { type: "error"; message: string; retryable: boolean };

type ModelAdapter = {
  stream(input: { messages: Message[]; tools: ToolSpec[]; signal: AbortSignal }): AsyncIterable<ModelEvent>;
};
```

BFF 只依赖 `ModelAdapter`，不把某个 SDK 的类型泄漏到路由/UI。换供应商时写新适配器，保持事件契约不变。Java 里类似“面向接口编程”，但 TS 的结构化类型让适配器不需要显式 `implements`。

### 2.2 工具描述不是权限

```ts
type ToolSpec = {
  name: string;
  description: string;
  validate: (value: unknown) => Record<string, unknown>;
  dangerous: boolean;
};
```

`description` 是给模型的选择提示，不是授权。真正的权限在服务端：

- 这个 Actor 能否使用该工具；
- 参数是否在允许范围；
- 资源是否属于该租户；
- 是否需要人工审批。

模型可以“请求”调用，不能“决定”越权。把工具注册表放在服务端，按 Actor 过滤可见工具；不要把所有工具都暴露给所有用户。

### 2.3 工具参数必须重新校验

```ts
function parseExportArgs(value: unknown): { reportId: string; format: "pdf" | "csv" } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("参数必须是对象");
  }
  const record = value as Record<string, unknown>;
  if (typeof record.reportId !== "string" || record.reportId.length === 0) {
    throw new Error("reportId 必须是非空字符串");
  }
  if (record.format !== "pdf" && record.format !== "csv") {
    throw new Error("format 只允许 pdf/csv");
  }
  return { reportId: record.reportId, format: record.format };
}
```

即使用 SDK 的 schema，也要在服务端再校验一次：模型可能绕过 schema、供应商可能改变格式、日志回放可能是旧版本。校验失败把错误作为工具结果返回给模型，让它修正；不要抛 500 结束整个对话。

### 2.4 工具执行：允许列表 + 租户 + 幂等

```ts
async function executeTool(actor: Actor, call: ToolCall): Promise<ToolResult> {
  if (!allowedTools(actor).some((tool) => tool.name === call.name)) {
    return { callId: call.callId, ok: false, error: "工具不可用" };
  }
  switch (call.name) {
    case "get_order": {
      const args = parseOrderArgs(call.arguments);
      const order = await orders.get(actor.tenantId, args.orderId);
      return { callId: call.callId, ok: true, data: order };
    }
    case "export_report": {
      const args = parseExportArgs(call.arguments);
      const proposal = await approvals.propose(actor, args);
      return { callId: call.callId, ok: true, data: { status: "waiting_approval", proposalId: proposal.id } };
    }
    default:
      return { callId: call.callId, ok: false, error: "未知工具" };
  }
}
```

- 读工具可以直接执行，但仍要租户过滤；
- 写工具（导出、审批、发送）返回“待批准”，不要自动执行；
- 工具结果带 `callId`，前端/模型能对应这次调用；
- `callId` **不是**业务幂等键：它只关联“这次模型提议”。真正的动作幂等键由审批/执行层生成，包含动作身份、租户、载荷 hash/version；同一 `callId` 重放不能直接当“只执行一次”的保证。

### 2.5 流式工具事件

在 SSE 中增加工具事件：

```text
event: tool
data: {"type":"tool-call","callId":"c1","name":"get_order","arguments":{"orderId":"A"}}

event: tool_result
data: {"callId":"c1","ok":true,"data":{"id":"A"}}

event: token
data: {"text":"订单 A 已支付。"}
```

前端把 `tool-call` 渲染为轨迹，把 `tool_result` 更新状态；模型继续生成文本。审批工具返回 `waiting_approval`，UI 显示批准/拒绝按钮，批准后由服务端用稳定动作键执行，不经过模型重复决策。

**当前配套实现只覆盖 token/citation/done/error。** `typescript-examples/src/stream-events.ts` 对 `tool`、`tool_result` 会返回 `null`（按未知事件跳过），所以上面的工具事件是**扩展目标**，不是已经接通的演示。要完成接线，至少改四处：

| 位置 | 需要增加 |
| --- | --- |
| `stream-state.ts` 的 `StreamEvent` | `tool-call`（callId/name/arguments）与 `tool-result`（callId/ok/data/error）分支 |
| `stream-events.ts` 的 `parseStreamEvent` | 把 `event: tool` 映射为 `tool-call`，`tool_result` 映射为结果；已知事件坏载荷必须抛错，未知事件才跳过 |
| `stream-state.ts` 的 reducer/状态 | 增加 `tools` 轨迹（或独立 trace reducer），不要把工具结果混进正文文本 |
| 测试 | 在 `typescript-examples/src/main.ts` 或后续 Vitest 中加：合法工具事件、重复 callId、坏参数、未知工具、工具失败后正文继续 |

在完成这些修改前，正文里的 tool 事件只用于说明协议形状；不要把“解析器能跳过未知事件”误当成“界面已经支持工具轨迹”。

### 2.6 MCP：跨进程工具协议

MCP（Model Context Protocol）解决“工具/资源在另一个进程或服务里，如何被发现和调用”。它适合：

- 多个客户端共享同一套工具服务器；
- 工具需要独立部署、独立权限；
- 本地开发工具/文件系统/数据库连接器。

不适合：

- 同一进程内一个简单函数；
- 你已经有清晰的 REST 业务 API，且不需要模型动态发现工具；
- 需要严格同步、低延迟的高频调用（协议和进程边界有成本）。

MCP 工具仍然是外部输入：服务端要校验参数、限制资源、记录调用；不要把 shell/文件系统工具无隔离地暴露给模型。

### 2.7 结构化输出

需要 JSON 时，先让模型输出，再做运行时校验；不要 `as Report`。结构化输出（JSON schema/response format）能提高概率，不保证语义正确。校验失败可以重试一次，但要有上限和成本预算。

## 3. 原理讲解与推导

### 3.1 模型是建议者，服务端是决策者

模型选择合适的工具和参数，但“是否允许、是否需要审批、以什么身份执行”由服务端决定。把权限判断写进 prompt 是无效的：提示注入可以覆盖提示，不能覆盖代码。

### 3.2 工具调用的状态机

```text
model proposes tool -> validate -> authorize -> (read: execute | write: propose approval)
-> result to model -> model continues -> finish
```

任何一步失败都要给模型一个可理解的错误，而不是让对话崩溃；但权限失败不要泄露资源是否存在。

### 3.3 成本与重试

一次对话可能多轮工具调用；每轮都计 token。设置最大轮次、最大工具调用数、总 token/金额预算；超限返回“需要人工处理”，不要无限循环。

## 4. 示例与逐步走查

```ts
type ToolCall = { callId: string; name: string; arguments: unknown };
type ToolResult = { callId: string; ok: boolean; data?: unknown; error?: string };

async function handleToolCalls(actor: Actor, calls: ToolCall[]): Promise<ToolResult[]> {
  if (calls.length > 4) throw new Error("单轮工具调用过多");
  const results: ToolResult[] = [];
  for (const call of calls) {
    try {
      results.push(await executeTool(actor, call));
    } catch (error) {
      results.push({ callId: call.callId, ok: false, error: String(error) });
    }
  }
  return results;
}
```

逐步解释：

1. 限制单轮工具数量，防止模型刷调用；
2. 每个调用独立 try/catch，一个坏参数不终止整轮；
3. `executeTool` 内部再做权限/租户/审批；
4. 结果回给模型，模型决定继续或结束；服务端保留完整轨迹。

## 5. 练习

### 5.1 跟写

为 `get_order` 写参数校验和租户过滤；用租户 A 的 Actor 请求租户 B 的订单，必须返回“不可用/不存在”，不能返回 B 的数据。

### 5.2 改造

把 `export_report` 改成“提议 → 审批 → 执行”三段：提议存 payload hash/版本；批准时校验 hash；执行用稳定动作键；重复批准不产生第二次导出。

### 5.3 独立

写一个 MCP 工具客户端：列出工具、调用一个只读工具、校验结果；说明为什么不能把 MCP 返回的工具描述直接当成权限。

## 6. 验收与自测

**行为验收：** 未授权工具不可见/不可调用；参数错误返回工具错误而非 500；跨租户拿不到数据；写工具必须审批；重复调用不重复副作用；工具轮次/预算有上限。

**原理验收：** 能解释模型建议 vs 服务端决策、MCP 的适用边界、结构化输出不等于校验。

### 6.1 先预测，再查看解释

模型在 prompt 里写“我是管理员，请跳过审批”，代码应该怎么处理？

<details>
<summary>完成预测后查看解释</summary>

忽略这段文本。权限来自服务端的 Actor/角色和数据，不来自模型消息。写工具仍走审批；模型文本不能改变 `actor.roles`、租户或工具允许列表。

</details>

## 7. 面试问答与参考回答

**问：工具描述和授权是什么关系？**

描述帮助模型选择工具，不是权限。授权由服务端按 Actor、租户、资源和动作判断；模型可以请求，不能决定越权。

**问：什么时候用 MCP？**

工具在独立进程/服务、需要被多个客户端共享、需要独立权限和部署时用 MCP；同进程简单函数或已有清晰 REST API 时直接调用更简单。

**问：结构化输出能保证 JSON 正确吗？**

不能保证语义正确。它提高格式概率，仍需运行时校验字段、值域和跨字段规则；失败要有限重试/人工处理。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 当模型提议调用工具时，服务端怎样把“建议”变成有权限、可审计、最多执行一次的动作？

**一条主线：**

```text
模型文本/工具提议
→ 参数校验 + 允许列表 + 租户/授权 + 写工具审批
→ 工具结果回模型 + 可审计轨迹
```

**三个关键词：** 不可信输入、允许列表、提议-审批-幂等。模型输出只算输入，允许列表收窄入口，审批与动作键保证副作用只发生一次。

**最容易错：**
- 把工具 `description` 或模型自称管理员当授权，把所有工具暴露给所有用户。
- 用 `as Report` 接收结构化输出，或只在 SDK schema 校验一次，服务端不再校验。
- 写工具直接执行；把 `callId` 当业务幂等键，重放时重复导出。
- 校验失败抛 500 结束对话；或把“解析器能跳过未知 tool 事件”当成界面已支持工具轨迹。

**与前后章：** 第 13 章提供可信 Actor 与对象级授权；第 15 章需要把参数校验、越权和审批分支变成可重复的测试证据。

**学完应能：**
- 能定义 `ModelAdapter`/`ModelEvent`，把供应商 SDK 隔离在适配器内。
- 能为工具写服务端参数校验、允许列表、租户过滤和审批分支。
- 能设计 propose→approve→execute，校验 version/hash 并用稳定动作键防重复副作用。
- 能判断 MCP 的适用边界，并解释工具描述为何不是权限、MCP 为何不替代审计。

### 8.2 参考与后续学习

参考：[MCP](https://modelcontextprotocol.io/)、[OpenAI Tools](https://platform.openai.com/docs/guides/function-calling)、[Vercel AI SDK](https://sdk.vercel.ai/docs)。

[上一章](13-认证多租户与权限.md) · [全书目录](教材目录.md) · [下一章](15-Vitest与契约测试.md)