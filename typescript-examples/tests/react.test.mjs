import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useAsyncData, useStreamingAnswer } from "../dist/hooks.js";

function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function mount(Probe) {
  const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost" });
  const previous = { window: globalThis.window, document: globalThis.document,
    IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const root = createRoot(document.getElementById("root"));
  return { render: props => act(() => root.render(React.createElement(React.StrictMode, null, React.createElement(Probe, props)))),
    async close() { await act(() => root.unmount()); dom.window.close(); Object.assign(globalThis, previous); } };
}
test("真实React Hook：A迟到取消不清空B缓冲，停止保留末尾文字", async () => {
  let api; const calls = [];
  const runner = (_input, receive, signal) => { const d = deferred(); calls.push({ ...d, receive, signal }); return d.promise; };
  function Probe() { api = useStreamingAnswer("fixture", () => ({}), "tenant-a:user-1:v1", runner, 10000); return null; }
  const view = mount(Probe);
  try {
    await view.render({});
    let first, second;
    await act(() => { first = api.start(); });
    await act(() => { second = api.start(); });
    await act(async () => { calls[1].receive({ type: "token", text: "B" }); calls[0].reject(new DOMException("old", "AbortError")); await first; });
    await act(async () => { calls[1].receive({ type: "done", answerId: "B", needsReview: true }); calls[1].resolve(); await second; });
    assert.equal(api.state.text, "B"); assert.equal(api.state.status, "done");
    let third;
    await act(() => { third = api.start(); calls[2].receive({ type: "token", text: "停止前" }); api.stop(); });
    assert.equal(api.state.text, "停止前"); assert.equal(api.state.status, "stopped");
    await act(async () => { calls[2].resolve(); await third; });
  } finally { await view.close(); }
});
test("真实React Hook：身份切换与退出不显示旧数据，旧回调不能提交", async () => {
  let api; const loads = [];
  const identity = { subjectId: "u", tenantId: "a", authVersion: "1", indexVersion: "1" };
  function Probe({ who }) {
    api = useAsyncData(who, "付款", "2026-01-01", () => { const d = deferred(); loads.push(d); return d.promise; });
    return null;
  }
  const view = mount(Probe);
  try {
    await view.render({ who: identity });
    // StrictMode执行setup/cleanup/setup，最后一个请求才属于当前运行。
    const first = loads.at(-1);
    await view.render({ who: { ...identity, tenantId: "b" } });
    const current = loads.at(-1);
    await act(async () => { first.resolve("tenant-a-secret"); await first.promise; });
    assert.notEqual(api.state.status, "success");
    await act(async () => { current.resolve("tenant-b-data"); await current.promise; });
    assert.equal(api.state.data, "tenant-b-data");
    await view.render({ who: null });
    assert.equal(api.state.status, "idle");
  } finally { await view.close(); }
});
