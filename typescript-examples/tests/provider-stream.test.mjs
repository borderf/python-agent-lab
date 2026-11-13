import { test } from "node:test";
import assert from "node:assert/strict";
import { OllamaStreamAdapter } from "../dist/provider-stream.js";

const encoder = new TextEncoder();
const line = value => JSON.stringify(value) + "\n";

test("Ollama NDJSON 跨字节分块仍还原中文 token", () => {
  const adapter = new OllamaStreamAdapter();
  const bytes = encoder.encode(line({ message: { content: "预付款" }, done: false }));
  const events = [];
  for (let i = 0; i < bytes.length; i += 1) events.push(...adapter.push(bytes.slice(i, i + 1)));
  events.push(...adapter.finish());
  assert.deepEqual(events, [{ type: "token", text: "预付款" }]);
});

test("Ollama done 映射结束原因与用量", () => {
  const adapter = new OllamaStreamAdapter();
  const events = adapter.push(encoder.encode(line({
    message: { role: "assistant", content: "" }, done: true, done_reason: "stop",
    prompt_eval_count: 12, eval_count: 3,
  })));
  assert.deepEqual(events, [{ type: "done", reason: "stop", usage: { inputTokens: 12, outputTokens: 3 } }]);
});

test("Ollama tool_calls 生成带 callId 的事件，参数保持原对象", () => {
  const adapter = new OllamaStreamAdapter();
  const events = adapter.push(encoder.encode(line({
    message: { tool_calls: [{ function: { name: "get_order", arguments: { orderId: "A" } } }] },
    done: false,
  })));
  assert.deepEqual(events, [{ type: "tool-call", callId: "ollama-call-1", name: "get_order",
    arguments: { orderId: "A" } }]);
});

test("Ollama error 行与坏 JSON 分类", () => {
  const adapter = new OllamaStreamAdapter();
  assert.deepEqual(adapter.push(encoder.encode(line({ error: "model not found" }))),
    [{ type: "error", message: "model not found", retryable: false }]);
  const broken = new OllamaStreamAdapter();
  assert.throws(() => broken.push(encoder.encode("not json\n")), /合法 JSON/);
});

test("Ollama 非法UTF-8与过长半行明确拒绝", () => {
  assert.throws(() => new OllamaStreamAdapter().push(new Uint8Array([0xff])), /encoded data|encoding/i);
  assert.throws(() => new OllamaStreamAdapter().push(encoder.encode("x".repeat(1_048_577))), /上限/);
});
