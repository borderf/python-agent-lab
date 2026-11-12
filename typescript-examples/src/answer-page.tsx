import { useStreamingAnswer, type StreamInput } from "./hooks.js";
import type { StreamRunner } from "./stream-controller.js";
import type { Citation } from "./stream-state.js";

export function AnswerPage({ endpoint, question, asOf, scopeKey, onOpenSource, runner }: {
  endpoint: string; question: string; asOf: string; scopeKey: string | null;
  onOpenSource: (citation: Citation) => void; runner?: StreamRunner<StreamInput>;
}) {
  const { state, start, stop } = useStreamingAnswer(endpoint, () => ({ question, as_of: asOf }), scopeKey, runner);
  return <main>
    <button type="button" disabled={scopeKey === null || !question.trim() || !asOf} onClick={() => void start()}>生成回答</button>
    <button type="button" disabled={state.status !== "connecting" && state.status !== "streaming"} onClick={stop}>停止</button>
    {state.status === "idle" ? <p>输入问题和业务日期后开始。</p> : <article>
      <p style={{ whiteSpace: "pre-wrap" }}>{state.text}</p>
      <ul aria-label="引用来源">{state.citations.map(item => <li key={JSON.stringify([item.sourceId, item.version, item.quote])}>
        <button type="button" onClick={() => onOpenSource(item)}>打开来源 {item.sourceId}</button>
        <blockquote>{item.quote}</blockquote>
      </li>)}</ul>
      {state.status === "connecting" && <p role="status">正在连接…</p>}
      {state.status === "stopped" && <p role="status">已停止，保留已生成内容。</p>}
      {state.status === "error" && <p role="alert">生成中断：{state.message}。部分内容尚未完成核验。</p>}
      {state.status === "done" && <p role="status">{state.needsReview ? "需要人工复核" : "生成完成，请核对来源"}</p>}
    </article>}
  </main>;
}
