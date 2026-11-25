# 第14章　AI SDK、工具调用与 MCP

[上一章](13-认证多租户与权限.md) · [全书目录](教材目录.md) · [下一章](15-Vitest与契约测试.md)

## 1. 学习目标与前置知识

能在 BFF 里接模型 SDK/HTTP，处理流式文本、工具调用、结构化输出和用量；能给工具加参数校验、允许列表、租户边界与人工审批；能判断什么时候用 MCP、什么时候直接调用。前置：第 5–6、11–13 章。

**本章从这里开始：** 模型提出“导出数据”时，服务端要先检查工具名、参数和用户权限，再决定是否执行；生成了一段JSON，也要先检查字段才能使用。导出、写数据库等操作会改变系统或对外产生结果，这里称为副作用。模型可以建议动作，程序负责检查和执行。

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

先让路由只认识`ModelAdapter`约定的输入和事件，再由适配器把供应商响应转换成这套格式。更换供应商时，主要修改适配器，页面和路由继续处理同样的事件。这样避免各处代码都依赖某个SDK的专用类型。TypeScript按结构判断类型兼容，所以对象即使没有写`implements`，只要符合接口要求，也可以作为适配器使用。

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

模型可以“请求”调用，不能“决定”越权。把工具注册表放在服务端，按 Actor 过滤可见工具；不要把所有工具都暴露给所有用户。这里的 `validate` 只演示统一入口；实际注册表应返回 `Result<T, E>` 或配合类型守卫保留具体参数类型，而不是把所有参数都退化成 `Record`。

### 2.3 工具参数必须重新校验

```ts
function parseExportArgs(value: unknown): { reportId: string; format: "pdf" | "csv" } {
  if (!isRecord(value)) throw new Error("参数必须是对象");
  const record = value;
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

最小客户端先完成**初始化、列工具、调用工具**三步。下面用JSON-RPC 2.0消息展示协议，不依赖具体SDK；`id`关联请求与响应，实际传输可使用SDK规定的stdio或HTTP方式：

```text
// initialize 请求
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"docpilot","version":"0.1"}}}

// initialize 响应（省略服务器附加能力）
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"policy-tools","version":"1.0"}}}

// tools/list 请求
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}

// tools/list 响应中的核心字段
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"search_policy","description":"按租户检索制度","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"asOf":{"type":"string"}},"required":["query","asOf"],"additionalProperties":false}}]}}

// tools/call 请求
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_policy","arguments":{"query":"付款期限","asOf":"2026-06-30"}}}

// tools/call 成功响应
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"docId\":\"policy\",\"version\":\"v2\"}"}],"isError":false}}
```

流程是：连接后发送`initialize`，记录协商版本与服务器能力，再发送SDK要求的`notifications/initialized`；需要工具时发送`tools/list`，把返回的`inputSchema`转成模型可见描述；模型选择工具后发送`tools/call`，由服务器执行。这里每条消息都是独立JSON文本，`//`行只用于讲解，不应发给服务器。**服务器声明支持工具，不代表客户端可以无条件调用**：客户端仍按当前Actor过滤工具、校验参数和租户；收到`isError:true`、协议错误或超时，都映射为有限、脱敏的工具失败。`text`内容也仍要解析并校验，不能因为来自MCP服务器就信任。

下面把“列出的工具”落到一次可检查调用，`toolName`与`args`都是外部输入：

```ts
async function callListedReadTool(
  mcp: { listTools(): Promise<{ name: string }[]>; callTool(input: { name: string; arguments: unknown }): Promise<{ content: { type: string; text?: string }[]; isError?: boolean }> },
  allowed: ReadonlySet<string>,
) {
  const tools = await mcp.listTools();
  const name = "search_policy";
  if (!allowed.has(name) || !tools.some((tool) => tool.name === name)) {
    throw new Error("tool_unavailable");
  }
  const result = await mcp.callTool({
    name,
    arguments: { query: "付款期限", asOf: "2026-06-30" },
  });
  if (result.isError) throw new Error("tool_failed");
  const text = result.content.find((item) => item.type === "text")?.text;
  if (!text) throw new Error("invalid_tool_result");
  const parsed: unknown = JSON.parse(text);
  if (typeof parsed !== "object" || parsed === null || !("docId" in parsed) || !("version" in parsed)) {
    throw new Error("invalid_tool_result");
  }
  return parsed;
}
```

真实接入还应把`allowed`与Actor、工具schema和租户查询绑定；这里只演示“先列出再调用、先过滤再执行、结果再次校验”的最小边界。

### 2.7 结构化输出

需要 JSON 时，先让模型输出，再做运行时校验；不要 `as Report`。结构化输出（JSON schema/response format）能提高概率，不保证语义正确。校验失败可以重试一次，但要有上限和成本预算。

### 2.8 最小工具序列：输入、判断与输出

模型发出一次`export_report`提议时，服务端按下面顺序处理。这里只展示一条调用，不假设工具执行器已经存在：

```text
输入 ToolCall
{callId:"c1", name:"export_report", arguments:{reportId:"r1", format:"pdf"}}
  ↓ 按Actor过滤允许列表
  ↓ parseExportArgs检查reportId与format
  ↓ 查询/授权确认r1属于actor.tenantId
  ↓ 写工具进入propose approval，不直接导出
输出 ToolResult
{callId:"c1", ok:true, data:{status:"waiting_approval", proposalId:"p1"}}
```

模型可以把结果继续用于生成说明，但UI必须显示“待审批”，不能显示“已导出”。若参数错误，输出`{callId:"c1", ok:false, error:"invalid_arguments"}`并让模型修正；若租户不符，返回统一的“工具不可用/资源不存在”，不泄露r1是否属于别人。

### 2.9 工具错误与HTTP错误不要混用

| 失败位置 | 返回给模型/前端 | HTTP层 | 后续动作 |
| --- | --- | --- | --- |
| 工具名不在允许列表 | `ok:false`，稳定错误码 | 对话请求仍可200 | 记录拒绝，不执行 |
| 参数形状/值域错误 | `ok:false`，指出可修正字段 | 不把单次工具失败变500 | 模型可重新提议 |
| 跨租户/无对象权限 | 统一不可用，不泄露存在性 | 不变 | 安全日志记拒绝原因 |
| 读工具依赖暂时失败 | `ok:false, retryable:true` | 不变 | 有限重试或结束 |
| 写工具等待审批 | waiting_approval状态 | 不变 | 等人工动作，不重复提议执行 |
| 请求本身未认证/坏JSON | 请求级错误体 | 401/422 | 不进入模型工具循环 |

现有`handleToolCalls`用`String(error)`把异常放进结果，这会把内部消息带给模型；实现时应改为稳定、脱敏的错误码，详细堆栈只进服务端日志。工具错误是对话内容，不等于整个HTTP请求失败。

### 2.10 SDK、自建适配器与MCP的对照

| 方式 | 适合解决 | 不自动提供 | 当前工程状态 |
| --- | --- | --- | --- |
| 供应商SDK | 模型消息、流事件、结构化输出 | 权限、租户、审批、幂等 | 未依赖AI SDK |
| 自建ModelAdapter | 统一内部事件，隔离供应商差异 | 运行时校验和工具安全 | 已有Ollama→ProviderEvent→SSE映射 |
| MCP客户端/服务器 | 跨进程发现与调用独立工具 | 工具权限、审计、参数值域 | 未依赖MCP，本章为设计练习 |

选型先看边界：工具在同一进程且只有几个函数，直接注册更简单；已有稳定REST API，直接调用更容易审计；多个客户端共享、独立部署和动态发现时再考虑MCP。无论哪种方式，模型返回的tool name/arguments都当作不可信输入。

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

### 3.4 callId、proposalId与动作键不是一回事

`callId`关联一次模型提议，可能因重试或流重放再次出现；`proposalId`关联一条审批记录；业务幂等键应描述“同一租户的同一动作和同一载荷”，例如：

```text
actionKey = hash(tenantId, actionType, reportId, version, payloadHash)
```

审批记录对actionKey设唯一约束。执行时先在本地事务中创建/认领动作账本，再调用外部导出；如果供应商支持幂等键，把同一actionKey传给供应商。没有供应商幂等能力时，本地只能保证“不发起第二次”，无法保证“第一次已执行但响应丢失”的恰好一次；这时要把账本置为待对账，查询供应商结果后再完成，不能盲目重试。

因此“重复approve不产生第二次导出”需要审批状态、唯一动作键、执行账本和供应商能力共同证明，仅把callId去重不够。

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

### 4.1 当前Ollama映射实际走到哪里

给定NDJSON行`{"message":{"content":"你"},"done":false}`，`OllamaStreamAdapter`产生`{type:"token",text:"你"}`，BFF输出`event: token`。给定`message.tool_calls`，适配器产生tool-call，BFF输出`event: tool`；但`stream-events.ts`把tool当未知事件返回null，所以当前React正文不会显示工具轨迹，更没有执行工具。

给定`done:true, done_reason:"stop", prompt_eval_count:12, eval_count:3`，适配器产生done和usage，BFF把它映射为`event: done`且needsReview=true。可是`parseStreamEvent`的done分支只保留answerId/needsReview，usage被丢弃；因此当前前端没有可用成本数据。length、unknown或提前EOF都映射error，不能算成功完成。

这些是源码行为推导，不是公网Ollama冒烟结果。接入真实SDK/供应商时，要另测其分块、取消、usage和工具schema。

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

| 操作 | 预期 | 证据 |
| --- | --- | --- |
| 模型提议未注册工具 | `ok:false`，执行函数调用数0 | 工具分发单测 |
| reportId为空/format=exe | 参数错误回模型，HTTP不因工具失败变为500 | 校验与handleToolCalls用例 |
| Actor A请求租户B订单 | 统一不可用，响应无B数据 | 租户过滤集成用例 |
| 模型提议export | waiting_approval，导出函数未调用 | 审批状态断言 |
| 同actionKey重复approve/execute | 仅一条账本/一次供应商请求 | 唯一约束、状态机与供应商幂等测试 |
| 单轮5个调用或超过总预算 | 拒绝后续，返回需人工处理 | 轮次/预算边界测试 |
| Ollama tool_calls进入当前页面 | 仅确认SSE有tool；当前解析器跳过 | `answer-stream.test.mjs`与`parseStreamEvent` |

工具执行、审批和MCP目前是本章扩展设计，没有现成端到端通过记录；不能把“BFF转发了tool事件”写成“工具已安全执行”。

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

**三个关键词：** 不可信输入、允许列表、提议-审批-幂等。模型只提议，服务端校验并授权；写动作用业务动作键和账本控制副作用。

**最容易错：**
- 把description/模型自称管理员当权限；参数只信SDK schema。
- 把callId当业务幂等键；本地账本未完成就盲目重试外部导出。
- 工具异常直接`String(error)`回模型；单次工具失败误变HTTP 500。
- 看到BFF输出tool就声称UI/执行器已支持；忽略usage会被当前解析器丢弃。

**与前后章：** 第13章提供Actor、租户和审批原则；第15章把这些拒绝、修正、重复和未覆盖边界变成测试。

**学完应能：** 从一条ToolCall推导每个检查与结果；区分工具错误/HTTP错误、callId/actionKey、SDK/适配器/MCP；说明当前实现缺口。

### 8.2 参考与后续学习

参考：[MCP](https://modelcontextprotocol.io/)、[OpenAI Tools](https://platform.openai.com/docs/guides/function-calling)、[Vercel AI SDK](https://sdk.vercel.ai/docs)。

[上一章](13-认证多租户与权限.md) · [全书目录](教材目录.md) · [下一章](15-Vitest与契约测试.md)
