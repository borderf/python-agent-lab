import { test } from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createBffServer } from "../dist/server.js";

test("Node HTTP 入口转发健康检查与身份错误", async () => {
  const server = createBffServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const base = `http://127.0.0.1:${address.port}`;
  try {
    const health = await fetch(`${base}/health`);
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { status: "ok" });
    const page = await fetch(`${base}/`);
    assert.equal(page.status, 200);
    assert.match(await page.text(), /DocPilot 搜索/);
    const script = await fetch(`${base}/app.js`);
    assert.equal(script.status, 200);
    assert.match(await script.text(), /\/api\/search/);
    const unauthorized = await fetch(`${base}/api/search`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "预付款", as_of: "2026-01-01" }),
    });
    assert.equal(unauthorized.status, 401);
  } finally {
    server.close();
    await once(server, "close");
  }
});