# 第06章　HTTP、SSE 与流式 AI 响应

[上一章](05-异步并发与取消.md) · [全书目录](教材目录.md) · [下一章](教材目录.md)

## 1. 学习目标与前置知识

能正确检查 HTTP 响应、解析 JSON 错误体，能用 `fetch` + `ReadableStream` 读取 SSE，处理跨 chunk 的行与 UTF-8 边界，支持中止，并知道流式响应为什么不能像普通请求那样重试。前置：第 1–5 章。

**本章从这里开始：** 模型回答不是一次性返回，而是逐段到达。浏览器收到的是字节流，可能把一行 SSE 切成两半，也可能把中文字符切在 UTF-8 中间。类型和异步都正确，界面仍可能显示乱码或丢字。

## 2. 基础知识讲解

### 2.1 HTTP 响应不是“有 body 就成功”

```ts
async function requestJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, init);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
  }
  return JSON.parse(text) as unknown;
}
```

`fetch` 只在网络失败时拒绝；404/500 仍是正常响应，必须检查 `response.ok` 或 `status`。错误体可能是 JSON，也可能是 HTML；先读文本，再按 `Content-Type` 解析，避免 `response.json()` 在错误页上再抛一次。

### 2.2 SSE 的线格式

SSE（`text/event-stream`）按行传输：

```text
event: token
data: {"text":"预"}

event: token
data: {"text":"付款"}

event: done
data: {"answerId":"A1","needsReview":true}
```

一条事件由若干 `field: value` 行组成，空行分隔事件。`data:` 后是一个空格，内容可能跨多行；`:` 开头是注释；`[DONE]` 是某些 API 的结束标记，不是 SSE 标准。解析器要按行缓冲，不能在任意 chunk 边界直接 `split("\n")` 后丢弃半行。

### 2.3 字节、行与事件分开处理

网络块不等于字符、行或事件。先用流式TextDecoder保留未完成的UTF-8字节，再缓冲完整行，最后由空行派发事件。LF、CRLF和CR都要识别；分隔完成前的EOF不能伪造成成功事件。

以下直接展示[同一份可执行源码](../../typescript-examples/src/sse.ts)，不是另写的参考答案：

<<< ../../typescript-examples/src/sse.ts

本客户端选择严格拒绝非法UTF-8，并给缓冲设置教学上限。协议这里只处理event、data和注释；没有实现id/retry重连。释放reader锁与取消剩余读取是两项操作；两者都不证明远端模型已停止计费。

### 2.4 线格式通过后，再校验业务事件

事件名来自event行；data不再额外要求type。token携带text，citation携带包含sourceId、version、quote的citation，done必须有answerId和needsReview，error必须有message和布尔retryable。未知事件名允许跳过，已知事件的坏载荷拒绝。

<<< ../../typescript-examples/src/stream-events.ts

## 3. 原理讲解与推导

### 3.1 流式响应的失败边界

普通JSON请求也要按操作幂等性、授权和预算判断是否重试。流式请求还需处理已显示文本与已发生费用：

- 用请求 ID/消息 ID 关联同一次生成；
- 续传需要生成开始时已取得的稳定任务ID，以及服务端定义的游标；字符数不自动等于游标；
- 不支持续传时，明确“重新生成”而不是“自动重试”；
- 浏览器取消本地等待后，由服务端继续传播取消并核对上游状态，不能由abort直接推断远端已停止。

### 3.2 背压与渲染

读取流比渲染快时，事件会堆积；每来一个 token 就触发一次 React 状态更新，可能造成大量重渲染。实际界面应批量合并（例如每 50ms 或每 N 个字符刷新一次），并保留最终完整文本。背压不是“读慢一点”这么简单，要考虑取消和内存上限。

### 3.3 类型边界

SSE 的 `data` 是字符串；`JSON.parse` 后是 `unknown`；必须用第 4 章的校验器。不要因为“这是模型输出”就信任它。`event` 名称是协议字段，可用字面量联合；未知事件应忽略但记录，不能崩溃。

## 4. 示例与逐步走查

先用测试构造的Response跑通，不请求并不存在的端点。当前Python两份教学服务仍返回一次性JSON；真实SSE是后续集成任务，不能把这里的客户端通过当作后端已经支持流式。

<<< ../../typescript-examples/src/stream-client.ts

按顺序走查：检查HTTP与媒体类型→解码并组装事件→校验载荷→通知调用方→检查终止。done结束时取消剩余读取；error先通知界面，再以StreamFailure拒绝Promise；无终止事件的EOF也拒绝。坏事件错误包含事件序号，不把敏感data原文放进提示。

调用方不重复把error记录成两次失败：reducer进入error终态后忽略后续错误动作。身份与来源语义仍由服务端验证，客户端校验不承担授权。

## 5. 练习

### 练习一：跟写

用 `readStream` 和 `createSseParser` 解析一段被拆成多个 chunk 的 SSE 文本，其中包含中文、`\r\n`、注释行和多行 `data:`；断言最终事件数与内容。

### 练习二：改造

给 `streamAnswer` 增加“每 50ms 批量回调”的包装，避免每个 token 都触发 UI 更新；保留 `done` 和 `error` 的即时性。

### 练习三：独立

设计断线恢复：先问任务ID何时取得、游标由谁产生。仅在done才收到answerId时，不能用它恢复中途断线；服务不支持续传就明确提供重新生成，并说明费用与重复风险。

## 6. 验收与自测

运行 `pnpm --dir typescript-examples test`，测试对同一字节流按1/2/3/5/7字节切块，也检查本章和附录的事件样本。

**行为验收：** 非 2xx 不进入流解析；错误 content-type 被拒绝；跨 chunk 行与中文不乱码；中止后不再回调；坏事件带序号/内容定位。

**原理验收：** 能解释 `TextDecoder` 的 `stream` 选项、SSE 空行分隔、流式重试的风险和背压。

### 6.1 先预测，再查看解释

一个 UTF-8 中文字符被拆到两个 chunk，`decoder.decode(chunk1)` 不加 `{stream:true}` 会怎样？

<details>
<summary>完成预测后查看解释</summary>

默认解码器可能产生替换字符U+FFFD；fatal模式会拒绝非法编码。stream:true等待后续字节，最终decode冲刷；若仍不完整，按所选策略替换或报错。

</details>

## 7. 面试问答与参考回答

**问：`fetch` 什么时候会 reject？**

通常只在网络层失败或请求被中止时；404/500 是已完成的 HTTP 响应，`fetch` 不会自动 reject，必须检查 `response.ok`。

**问：SSE 和 WebSocket 怎么选？**

SSE在HTTP响应上单向推送，WebSocket支持双向消息。原生EventSource不能任意设置Authorization头；fetch流可用POST和请求头，但需自行解析与恢复。代理缓冲、超时、认证与CORS均需按实际环境验证。

**问：流式响应为什么不能直接重试？**

已经渲染/计费的部分无法撤回，重试可能重复文本或重复调用模型。需要请求 ID、游标续传或明确“重新生成”，并处理取消与服务端清理。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 模型回答逐段到达，一行 SSE 可能被切成两半，中文字符也可能被切在 UTF-8 中间——到哪一步才算一条完整事件？

**一条主线：**

```text
HTTP 状态与 content-type → 字节流 → TextDecoder(stream) → 行缓冲/空行分派 → 业务事件校验 → 渲染或中止
```

**三个关键词：** SSE、增量解析、失败边界。SSE 以空行分隔事件，增量解析要跨 chunk 保住字节和半行，失败边界决定续传、重新生成还是放弃。

**最容易错：**

- 200 就当成功，不读错误体，也忽略 error 事件、错误的 content-type 和没有 done 的断流。
- 直接 `split("\n")` 丢半行，或 `TextDecoder` 不加 `{stream:true}` 让中文变 U+FFFD。
- 只认 LF，漏掉 CRLF 和 CR；未知事件名直接崩溃，或 EOF 前没有终止事件却当成正常完成。
- 把流式请求当普通请求自动重试，重复渲染、重复计费。

**与前后章：** 上一章的 signal 用于取消 reader，超时与重试边界继续沿用；下一章需要把解析器和事件类型打包成可发布的 ESM 模块。

**学完应能：**

- 用 1/2/3/5/7 字节切块喂同一个解析器，事件数与内容不变；
- 在 error 事件后先通知界面，再以 `StreamFailure` 拒绝并取消剩余读取；
- 解释为什么客户端 abort 不等于远端模型停止计费；
- 给 token 渲染加 50ms 批量，同时保住 done 和 error 的即时性。

### 8.2 参考与后续学习

参考：[Fetch API](https://developer.mozilla.org/docs/Web/API/Fetch_API)、[Server-sent events](https://developer.mozilla.org/docs/Web/API/Server-sent_events)、[TextDecoder](https://developer.mozilla.org/docs/Web/API/TextDecoder)。

[上一章](05-异步并发与取消.md) · [全书目录](教材目录.md) · [第 7 章](07-模块构建与工程化.md)
