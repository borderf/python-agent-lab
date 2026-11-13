import { test } from "node:test";
import assert from "node:assert/strict";
import { createBff } from "../dist/bff.js";

const authenticate = async token => token === "demo" ? { tenantId: "a", upstreamToken: "server-token" } : null;
const headers = { Authorization: "Bearer demo", "Content-Type": "application/json" };
function app(fetcher) {
  return createBff({ upstreamUrl: "https://python.invalid", mode: "core", authenticate, fetcher, timeoutMs: 1000,
    ollama: { upstreamUrl: "https://fixture.invalid", model: "fixture-model", apiKey: "model-key" } });
}
function ndjson(lines) {
  return new Response(new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      for (const line of lines) controller.enqueue(encoder.encode(JSON.stringify(line) + "\n"));
      controller.close();
    },
  }), { headers: { "Content-Type": "application/x-ndjson" } });
}

test("BFF 把 Ollama NDJSON 映射为应用 SSE token/done", async () => {
  const server = app(async () => ndjson([
    { message: { role: "assistant", content: "你" }, done: false },
    { message: { role: "assistant", content: "好" }, done: false },
    { message: { role: "assistant", content: "" }, done: true, done_reason: "stop", eval_count: 2 },
  ]));
  const response = await server.request("/api/answer", {
    method: "POST", headers, body: JSON.stringify({ question: "预付款" }),
  });
  assert.equal(response.status, 200);
  const text = await response.text();
  assert.match(text, /event: token[\s\S]*"你"/);
  assert.match(text, /event: token[\s\S]*"好"/);
  assert.match(text, /event: done/);
  assert.match(text, /needsReview":true/);
});

test("BFF 将供应商错误转成 SSE error，坏输入仍是422", async () => {
  const server = app(async () => new Response(null, { status: 503 }));
  const response = await server.request("/api/answer", {
    method: "POST", headers, body: JSON.stringify({ question: "预付款" }),
  });
  assert.equal(response.status, 200);
  assert.match(await response.text(), /event: error/);
  const bad = await server.request("/api/answer", {
    method: "POST", headers, body: JSON.stringify({ question: "预付款", tenant_id: "b" }),
  });
  assert.equal(bad.status, 422);
});

test("BFF 将完整 tool_calls 转成 tool 事件，不在流中执行", async () => {
  const server = app(async () => ndjson([
    { message: { tool_calls: [{ function: { name: "get_order", arguments: { orderId: "A" } } }] }, done: false },
    { message: {}, done: true, done_reason: "stop" },
  ]));
  const response = await server.request("/api/answer", {
    method: "POST", headers, body: JSON.stringify({ question: "查订单" }),
  });
  const text = await response.text();
  assert.match(text, /event: tool/);
  assert.match(text, /"name":"get_order"/);
  assert.match(text, /event: done/);
});

test("模型配置独立于检索地址与凭据；未配置时不请求上游", async () => {
  let calls = 0;
  const server = app(async (url, init) => {
    calls++;
    assert.equal(url, "https://fixture.invalid/api/chat");
    assert.equal(new Headers(init.headers).get("authorization"), "Bearer model-key");
    assert.equal(JSON.parse(init.body).model, "fixture-model");
    return ndjson([{ done: true, done_reason: "stop" }]);
  });
  await (await server.request("/api/answer", { method: "POST", headers,
    body: JSON.stringify({ question: "预付款" }) })).text();
  const disabled = createBff({ upstreamUrl: "https://python.invalid", mode: "core", authenticate,
    fetcher: async () => { throw new Error("不应请求上游"); } });
  assert.equal((await disabled.request("/api/answer", { method: "POST", headers,
    body: JSON.stringify({ question: "预付款" }) })).status, 503);
  assert.equal(calls, 1);
});

test("提前EOF、length与未知结束原因均不能冒充done", async () => {
  for (const end of [null, "length", "other"]) {
    const lines = [{ message: { content: "部分内容" }, done: false }];
    if (end !== null) lines.push({ done: true, done_reason: end });
    const response = await app(async () => ndjson(lines)).request("/api/answer", {
      method: "POST", headers, body: JSON.stringify({ question: "预付款" }),
    });
    const text = await response.text();
    assert.match(text, /部分内容/);
    assert.match(text, /event: error/);
    assert.doesNotMatch(text, /event: done/);
  }
});

test("坏供应商JSON仍取消reader并报告失败", async () => {
  let cancelled = false;
  const server = app(async () => new Response(new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode("broken\n")); },
    cancel() { cancelled = true; },
  })));
  const response = await server.request("/api/answer", { method: "POST", headers,
    body: JSON.stringify({ question: "预付款" }) });
  assert.match(await response.text(), /event: error/);
  assert.equal(cancelled, true);
});
