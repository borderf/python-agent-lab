import { test } from "node:test";
import { parseAnswer } from "../dist/contracts.js";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createSseParser } from "../dist/sse.js";
import { streamAnswer, StreamFailure } from "../dist/stream-client.js";
import { parseStreamEvent } from "../dist/stream-events.js";
import { reduceAnswer } from "../dist/stream-state.js";
import { LatestQuery, searchKey } from "../dist/query.js";
import { mapLimit } from "../dist/map-limit.js";
import { StreamController } from "../dist/stream-controller.js";

const done = 'event: done\ndata: {"answerId":"A1","needsReview":true}\n\n';
const token = 'event: token\ndata: {"text":"中文😀"}\n\n';
function fetchStream(text, size = 1) {
  const bytes = new TextEncoder().encode(text);
  return async () => new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += size) controller.enqueue(bytes.slice(i, i + size));
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

test("SSE字节分块、UTF-8和三种换行产生同样事件", async () => {
  for (const newline of ["\n", "\r\n", "\r"]) for (const size of [1, 2, 3, 5, 7]) {
    const events = [];
    await streamAnswer("fixture", {}, e => events.push(e), new AbortController().signal,
      fetchStream((token + done).replaceAll("\n", newline), size));
    assert.deepEqual(events.map(e => e.type), ["token", "done"]);
    assert.equal(events[0].text, "中文😀");
  }
});
test("SSE提前结束、坏JSON和错误事件都拒绝Promise", async () => {
  for (const text of [token, 'event: token\ndata: bad\n\n',
    'event: error\ndata: {"message":"failed","retryable":false}\n\n']) {
    await assert.rejects(streamAnswer("fixture", {}, () => {}, new AbortController().signal, fetchStream(text)));
  }
});
test("已知事件严格校验；未知事件名可跳过", () => {
  assert.equal(parseStreamEvent("heartbeat", "not json"), null);
  for (const [name, body] of [["done", { answerId: "A" }], ["citation", { sourceId: "x" }],
    ["error", { message: "x", retryable: "true" }]]) {
    assert.throws(() => parseStreamEvent(name, JSON.stringify(body)));
  }
});
test("done后取消剩余流，不接受迟到token", async () => {
  let cancelled = false;
  const events = [];
  const fetcher = async () => new Response(new ReadableStream({
    start(c) { c.enqueue(new TextEncoder().encode(done + token)); },
    cancel() { cancelled = true; },
  }), { headers: { "Content-Type": "text/event-stream" } });
  await streamAnswer("fixture", {}, e => events.push(e), new AbortController().signal, fetcher);
  assert.deepEqual(events.map(e => e.type), ["done"]);
  assert.equal(cancelled, true);
});
test("没有引用却宣称无需复核时拒绝完成", async () => {
  await assert.rejects(streamAnswer("fixture", {}, () => {}, new AbortController().signal,
    fetchStream(done.replace("true", "false"))), StreamFailure);
});
test("多行data与注释遵守线格式", () => {
  const result = [];
  const parser = createSseParser(e => result.push(e));
  [":ping", "event:", "data: first", "data:  second", ""].forEach(parser);
  assert.deepEqual(result, [{ event: "message", data: "first\n second" }]);
});
test("正文和附录中的每个基础SSE样本都通过业务解析", async () => {
  for (const name of ["06-HTTP与流式响应.md", "附录B-与Python后端的契约.md"]) {
    const text = await readFile(new URL(`../../docs/typescript-book/${name}`, import.meta.url), "utf8");
    const fixtures = [...text.matchAll(/```text\n(event:[\s\S]*?)```/g)];
    assert.ok(fixtures.length > 0);
    for (const match of fixtures) {
      const events = [];
      const parser = createSseParser(e => events.push(parseStreamEvent(e.event, e.data)));
      (match[1].trimEnd() + "\n\n").split("\n").forEach(parser);
      assert.ok(events.length > 0 && events.every(Boolean));
    }
  }
});
test("同源同版本保留不同引文，完全相同的引文去重", () => {
  let state = reduceAnswer({ status: "idle" }, { type: "start" });
  for (const quote of ["条款甲", "条款乙", "条款甲"]) state = reduceAnswer(state, {
    type: "event", event: { type: "citation", citation: { sourceId: "s", version: "1", quote } },
  });
  assert.equal(state.citations.length, 2);
});
test("停止后迟到事件保持终止态", () => {
  let state = reduceAnswer({ status: "idle" }, { type: "start" });
  state = reduceAnswer(state, { type: "stop" });
  assert.deepEqual(reduceAnswer(state, { type: "event", event: { type: "done", answerId: "old", needsReview: true } }), state);
});
test("mapLimit处理undefined、有界并发并保持输入顺序", async () => {
  let active = 0, peak = 0, calls = 0;
  const values = await mapLimit([1, undefined, 3], 2, async value => {
    calls++; peak = Math.max(peak, ++active);
    await new Promise(resolve => setTimeout(resolve, 1));
    active--;
    return String(value);
  });
  assert.equal(calls, 3); assert.equal(peak, 2);
  assert.deepEqual(values, ["1", "undefined", "3"]);
  for (const invalid of [0, -1, 0.5, Infinity]) await assert.rejects(mapLimit([1], invalid, async x => x), RangeError);
});
test("忽略取消的旧查询也不能覆盖新查询", async () => {
  let state;
  const query = new LatestQuery(value => { state = value; });
  const a = deferred(), b = deferred();
  const first = query.run("A", () => a.promise), second = query.run("B", () => b.promise);
  b.resolve("B-result"); await second; a.resolve("A-result"); await first;
  assert.deepEqual(state, { status: "success", key: "B", data: "B-result" });
  query.cancel(); assert.equal(state.status, "idle");
});
test("key区分租户、主体与撤权版本", () => {
  const base = { tenantId: "a", subjectId: "u", authVersion: "1", indexVersion: "1" };
  const key = searchKey(base, "付款", "2026-01-01");
  for (const changed of [{ tenantId: "b" }, { subjectId: "v" }, { authVersion: "2" }]) {
    assert.notEqual(searchKey({ ...base, ...changed }, "付款", "2026-01-01"), key);
  }
});
test("旧取消的catch不能清空新一轮的缓冲", async () => {
  const calls = [], states = [];
  const controller = new StreamController((_input, receive) => {
    const d = deferred(); calls.push({ ...d, receive }); return d.promise;
  }, state => states.push(state), 10000);
  const a = controller.start({}, "a"), b = controller.start({}, "a");
  calls[1].receive({ type: "token", text: "B" });
  calls[0].reject(new DOMException("old cancelled", "AbortError")); await a;
  calls[1].receive({ type: "done", answerId: "B", needsReview: true }); calls[1].resolve(); await b;
  assert.equal(states.at(-1).text, "B"); assert.equal(states.at(-1).status, "done");
  controller.dispose();
});
test("外部回答只投影公开字段，稀疏引用数组不能绕过校验", () => {
  const citation = { sourceId: "s", quote: "原文", accessToken: "internal-only" };
  const result = parseAnswer({ answer: "回答", citations: [citation], needsReview: true });
  assert.equal(result.ok, true);
  assert.deepEqual(result.value.citations, [{ sourceId: "s", quote: "原文" }]);
  citation.quote = "修改";
  assert.equal(result.value.citations[0].quote, "原文");
  assert.equal(parseAnswer({ answer: "回答", citations: new Array(1), needsReview: false }).ok, false);
});
