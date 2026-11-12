import { useId, useState } from "react";
import { useAsyncData } from "./hooks.js";
import type { QueryIdentity } from "./query.js";
import type { SearchHit } from "./search-contract.js";

export function SearchPage({ identity, load, onOpenSource }: {
  identity: QueryIdentity | null;
  load: (question: string, asOf: string, signal: AbortSignal) => Promise<SearchHit[]>;
  onOpenSource: (hit: SearchHit) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState("");
  const [date, setDate] = useState("");
  const [submitted, setSubmitted] = useState<{ question: string; date: string } | null>(null);
  const { state, retry } = useAsyncData(submitted ? identity : null, submitted?.question ?? "",
    submitted?.date ?? "", signal => load(submitted?.question ?? "", submitted?.date ?? "", signal));
  return <main>
    <form onSubmit={event => {
      event.preventDefault();
      if (!identity || !draft.trim() || !date) return;
      if (submitted?.question === draft.trim() && submitted.date === date) retry();
      else setSubmitted({ question: draft.trim(), date });
    }}>
      <label htmlFor={`${id}-question`}>问题</label>
      <input id={`${id}-question`} value={draft} onChange={e => setDraft(e.target.value)} />
      <label htmlFor={`${id}-date`}>业务日期</label>
      <input id={`${id}-date`} type="date" value={date} onChange={e => setDate(e.target.value)} />
      <button type="submit" disabled={!identity || !draft.trim() || !date}>搜索</button>
    </form>
    {!identity && <p>请先建立会话。</p>}
    {state.status === "loading" && <p role="status">搜索中…</p>}
    {state.status === "error" && <div role="alert"><p>{state.message}</p><button onClick={retry}>重试</button></div>}
    {state.status === "success" && (state.data.length === 0 ? <p>没有找到相关条款。</p> :
      <ul aria-label="搜索结果">{state.data.map(hit => <li key={JSON.stringify([hit.sourceId, hit.version, hit.quote])}>
        <button type="button" onClick={() => onOpenSource(hit)}>打开来源 {hit.sourceId}</button>
        <span>版本 {hit.version}</span><blockquote>{hit.quote}</blockquote>
      </li>)}</ul>)}
  </main>;
}
