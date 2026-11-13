import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { SearchPage } from "./search-page.js";
import type { SearchHit } from "./search-contract.js";
import type { QueryIdentity } from "./query.js";
import { streamAnswer } from "./stream-client.js";
import { useStreamingAnswer, type StreamInput } from "./hooks.js";
import type { StreamRunner } from "./stream-controller.js";

const developmentIdentity: QueryIdentity = {
  subjectId: "demo-user",
  tenantId: "a",
  authVersion: "dev-1",
  indexVersion: "dev-1",
};

async function loadHits(question: string, asOf: string, signal: AbortSignal): Promise<SearchHit[]> {
  const response = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer demo" },
    body: JSON.stringify({ question, as_of: asOf }),
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null
      && "error" in payload && typeof (payload as { error?: { message?: unknown } }).error?.message === "string"
      ? (payload as { error: { message: string } }).error.message
      : `请求失败（${response.status}）`;
    throw new Error(message);
  }
  if (typeof payload !== "object" || payload === null || !("items" in payload) || !Array.isArray(payload.items)) {
    throw new Error("BFF 返回结构不符合契约");
  }
  return payload.items as SearchHit[];
}

function SourcePanel({ hit }: { hit: SearchHit | null }) {
  if (!hit) return null;
  const location = hit.location.kind === "chunk"
    ? `片段 ${hit.location.chunkId}，偏移 ${hit.location.start}–${hit.location.end}`
    : `章节 ${hit.location.section}`;
  return <article aria-label="来源详情">
    <h2>{hit.title}</h2>
    <p>来源 {hit.sourceId}，版本 {hit.version}</p>
    <blockquote>{hit.quote}</blockquote>
    <p>{location}</p>
  </article>;
}

const developmentStream: StreamRunner<StreamInput> = (input, receive, signal) => {
  const withAuth: typeof fetch = (url, init) => {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", "Bearer demo");
    return fetch(url, { ...init, headers });
  };
  return streamAnswer(input.url, input.body, receive, signal, withAuth);
};

function AnswerPanel() {
  const [question, setQuestion] = useState("预付款比例是多少？");
  // 与教材第10章使用同一控制器：旧请求失效、批量刷新、停止保留内容、卸载取消。
  const { state, start, stop } = useStreamingAnswer("/api/answer",
    () => ({ question: question.trim() }), "development-demo", developmentStream);

  return <section aria-label="流式回答">
    <h2>流式回答</h2>
    <p>独立模型协议演示：未接入检索和引用校验，内容需要复核。</p>
    <label htmlFor="answer-question">问题</label>
    <input id="answer-question" value={question} onChange={event => setQuestion(event.target.value)} />
    <button type="button" disabled={Array.from(question.trim()).length < 2} onClick={() => void start()}>开始回答</button>
    <button type="button" disabled={state.status !== "connecting" && state.status !== "streaming"} onClick={stop}>停止</button>
    <p role="status">{state.status === "streaming" ? "生成中…" : state.status}</p>
    {state.status === "error" && <p role="alert">{state.message}</p>}
    {state.status === "done" && <p>生成完成，需人工复核。</p>}
    <article aria-live="polite" style={{ whiteSpace: "pre-wrap" }}>{state.status === "idle" ? "" : state.text}</article>
  </section>;
}

function App() {
  const [source, setSource] = useState<SearchHit | null>(null);
  return <>
    <SearchPage identity={developmentIdentity} load={loadHits} onOpenSource={setSource} />
    <SourcePanel hit={source} />
    <AnswerPanel />
  </>;
}

const root = document.querySelector("#root");
if (!root) throw new Error("缺少 #root");
createRoot(root).render(<StrictMode><App /></StrictMode>);
