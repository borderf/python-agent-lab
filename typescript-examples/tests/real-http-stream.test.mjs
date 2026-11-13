import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { createBff } from "../dist/bff.js";
import { createBffServer } from "../dist/server.js";

const authenticate = async token => token === "demo" ? { tenantId: "a", upstreamToken: "server-token" } : null;

test("真实 HTTP：BFF → 假 Ollama NDJSON → 应用 SSE", async () => {
  let release;
  const finish = new Promise(resolve => { release = resolve; });
  const upstream = createServer((req, res) => {
    assert.equal(req.url, "/api/chat");
    assert.equal(req.headers.authorization, "Bearer model-key");
    res.writeHead(200, { "Content-Type": "application/x-ndjson" });
    res.write(JSON.stringify({ message: { content: "预付款" }, done: false }) + "\n");
    void finish.then(() => {
      res.end(JSON.stringify({ message: { content: "20%" }, done: true, done_reason: "stop" }) + "\n");
    });
  });
  upstream.listen(0, "127.0.0.1");
  await once(upstream, "listening");
  const upstreamAddress = upstream.address();
  assert.ok(upstreamAddress && typeof upstreamAddress === "object");
  const app = createBff({
    upstreamUrl: `http://127.0.0.1:${upstreamAddress.port}`, mode: "core",
    ollama: { upstreamUrl: `http://127.0.0.1:${upstreamAddress.port}`, model: "fixture", apiKey: "model-key" },
    authenticate, timeoutMs: 1000,
  });
  const bff = createBffServer({ app });
  bff.listen(0, "127.0.0.1");
  await once(bff, "listening");
  const address = bff.address();
  assert.ok(address && typeof address === "object");
  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/api/answer`, {
      method: "POST",
      headers: { Authorization: "Bearer demo", "Content-Type": "application/json" },
      body: JSON.stringify({ question: "预付款" }),
      signal: AbortSignal.timeout(3000),
    });
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type") ?? "", /text\/event-stream/);
    const reader = response.body.getReader();
    const first = await reader.read();
    assert.equal(first.done, false);
    const initial = new TextDecoder().decode(first.value);
    assert.match(initial, /预付款/); // 上游尚未结束，就必须读到首段。
    release();
    let text = initial;
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      text += new TextDecoder().decode(next.value);
    }
    reader.releaseLock();
    assert.match(text, /event: token/);
    assert.match(text, /预付款/);
    assert.match(text, /20%/);
    assert.match(text, /event: done/);
  } finally {
    release();
    bff.close();
    upstream.close();
    await Promise.all([once(bff, "close"), once(upstream, "close")]);
  }
});

test("真实 HTTP：下游停止读取会取消上游连接", async () => {
  let disconnected;
  const closed = new Promise(resolve => { disconnected = resolve; });
  const upstream = createServer((req, res) => {
    res.once("close", disconnected);
    res.writeHead(200, { "Content-Type": "application/x-ndjson" });
    res.write(JSON.stringify({ message: { content: "第一段" }, done: false }) + "\n");
  });
  upstream.listen(0, "127.0.0.1");
  await once(upstream, "listening");
  const address = upstream.address();
  const bff = createBffServer({ app: createBff({ upstreamUrl: "http://python.invalid", mode: "core",
    authenticate, timeoutMs: 10000,
    ollama: { upstreamUrl: `http://127.0.0.1:${address.port}`, model: "fixture" } }) });
  bff.listen(0, "127.0.0.1");
  await once(bff, "listening");
  let timer;
  try {
    const response = await fetch(`http://127.0.0.1:${bff.address().port}/api/answer`, {
      method: "POST", headers: { Authorization: "Bearer demo", "Content-Type": "application/json" },
      body: JSON.stringify({ question: "预付款" }), signal: AbortSignal.timeout(3000),
    });
    const reader = response.body.getReader();
    assert.equal((await reader.read()).done, false);
    await reader.cancel();
    reader.releaseLock();
    await Promise.race([closed, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("下游取消未传到上游")), 2000);
    })]);
  } finally {
    clearTimeout(timer);
    bff.closeAllConnections();
    upstream.closeAllConnections();
    await Promise.all([new Promise(resolve => bff.close(resolve)), new Promise(resolve => upstream.close(resolve))]);
  }
});
