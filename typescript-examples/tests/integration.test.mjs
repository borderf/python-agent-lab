import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createBff } from "../dist/bff.js";
import { forwardSearch, RequestCancelled, UpstreamFailure } from "../dist/transport.js";
import { createDocumentStore } from "../dist/documents.js";
import { parseSearchResponse } from "../dist/search-contract.js";

const requestBody = { question: "预付款", as_of: "2026-01-01" };
const raw = { source_id: "policy-a", version: "1", title: "付款制度", text: "😀制度：预付款20%。",
  tenant_id: "a", valid_from: "2026-01-01", valid_to: null,
  chunk_id: '["a","policy-a","1",0]', start: 0, end: 11 };
const authenticate = async token => token === "demo" ? { tenantId: "a", upstreamToken: "server-token" } : null;
const headers = { Authorization: "Bearer demo", "Content-Type": "application/json" };
function app(fetcher, timeoutMs = 1000) {
  return createBff({ upstreamUrl: "https://fixture.invalid", mode: "core", authenticate, fetcher, timeoutMs });
}
function waitForAbort(_url, options) {
  return new Promise((_resolve, reject) => {
    if (options.signal.aborted) reject(options.signal.reason);
    else options.signal.addEventListener("abort", () => reject(options.signal.reason), { once: true });
  });
}
test("Hono合法搜索走可信上游身份，输出显式映射", async () => {
  const server = app(async (_url, init) => {
    assert.equal(init.headers.Authorization, "Bearer server-token");
    assert.deepEqual(JSON.parse(init.body), requestBody);
    return Response.json({ items: [raw] });
  });
  const response = await server.request("/api/search", { method: "POST", headers, body: JSON.stringify(requestBody) });
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.items[0].quote, raw.text);
  assert.equal(result.items[0].location.end, 11);
  assert.ok(response.headers.get("X-Request-ID"));
});
test("Hono拒绝无身份、伪造租户、坏JSON与不存在的日期", async () => {
  const server = app(async () => { throw new Error("不该转发"); });
  assert.equal((await server.request("/api/search", { method: "POST" })).status, 401);
  for (const value of [{ ...requestBody, tenant_id: "b" }, { ...requestBody, as_of: "2026-02-30" }]) {
    assert.equal((await server.request("/api/search", { method: "POST", headers, body: JSON.stringify(value) })).status, 422);
  }
  assert.equal((await server.request("/api/search", { method: "POST", headers, body: "bad" })).status, 422);
});
test("Hono按总时限返回504，上游422不改成502", async () => {
  assert.equal((await app(waitForAbort, 5).request("/api/search", {
    method: "POST", headers, body: JSON.stringify(requestBody),
  })).status, 504);
  assert.equal((await app(async () => new Response(null, { status: 422 })).request("/api/search", {
    method: "POST", headers, body: JSON.stringify(requestBody),
  })).status, 422);
});
test("客户端取消与预算超时分开，AbortError名字不充当来源", async () => {
  const client = new AbortController(); client.abort();
  await assert.rejects(forwardSearch("fixture", "token", requestBody, client.signal, waitForAbort, 10), RequestCancelled);
  await assert.rejects(forwardSearch("fixture", "token", requestBody, new AbortController().signal,
    waitForAbort, 5), e => e instanceof UpstreamFailure && e.status === 504);
});
test("Python两份HTTP响应夹具都通过适配，缺字段不静默默认", async () => {
  for (const mode of ["core", "persistent"]) {
    const fixture = JSON.parse(await readFile(new URL(`./fixtures/search-${mode}.json`, import.meta.url), "utf8"));
    const result = parseSearchResponse(fixture, mode);
    assert.equal(result.items[0].location.kind, mode === "core" ? "chunk" : "source");
    const broken = structuredClone(fixture); delete broken.items[0].text;
    assert.throws(() => parseSearchResponse(broken, mode));
  }
});
test("SQLite+Drizzle半开日期、租户隔离、重复与冲突", async () => {
  const store = await createDocumentStore();
  const first = { id: "1", tenantId: "a", sourceId: "s", version: "1", title: "制度", body: "旧内容",
    validFrom: "2026-01-01", validTo: "2026-07-01" };
  try {
    assert.equal(store.insert(first).status, "inserted");
    assert.equal(store.insert({ ...first, id: "retry" }).status, "duplicate");
    assert.throws(() => store.insert({ ...first, id: "other", body: "篡改" }), /冲突/);
    assert.equal(store.visible("a", "2026-06-30").length, 1);
    assert.equal(store.visible("a", "2026-07-01").length, 0);
    assert.equal(store.visible("b", "2026-06-30").length, 0);
    const restored = await createDocumentStore(store.export());
    try { assert.equal(restored.visible("a", "2026-06-30")[0].body, "旧内容"); }
    finally { restored.close(); }
  } finally { store.close(); }
});
test("SQLite批量冲突回滚已插入的前半批", async () => {
  const store = await createDocumentStore();
  const row = { id: "1", tenantId: "a", sourceId: "s", version: "1", title: "制度", body: "内容",
    validFrom: "2026-01-01", validTo: null };
  try {
    assert.throws(() => store.importBatch([row, { ...row, id: "2", body: "冲突" }]), /冲突/);
    assert.equal(store.visible("a", "2026-01-01").length, 0);
  } finally { store.close(); }
});
