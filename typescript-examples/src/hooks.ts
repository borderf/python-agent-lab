import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LatestQuery, searchKey, type QueryIdentity, type QueryState } from "./query.js";
import { StreamController, type StreamRunner } from "./stream-controller.js";
import { streamAnswer } from "./stream-client.js";
import type { AnswerState } from "./stream-state.js";

export type StreamInput = { url: string; body: unknown };
const remoteStream: StreamRunner<StreamInput> = (input, receive, signal) =>
  streamAnswer(input.url, input.body, receive, signal);

// #region stream-hook
export function useStreamingAnswer(url: string, body: () => unknown, scope: string | null,
  runner: StreamRunner<StreamInput> = remoteStream, flushMs = 50) {
  const [envelope, setEnvelope] = useState<{ state: AnswerState; scope: string | null }>({
    state: { status: "idle" }, scope: null,
  });
  const bodyRef = useRef(body);
  bodyRef.current = body;
  const controller = useMemo(() => new StreamController(runner,
    (state, owner) => setEnvelope({ state, scope: owner }), flushMs), [runner, flushMs]);
  const key = scope === null ? null : JSON.stringify([scope, url]);
  useEffect(() => {
    controller.reset(key);
    return () => controller.dispose();
  }, [controller, key]);
  const start = useCallback(async () => {
    if (key !== null) await controller.start({ url, body: bodyRef.current() }, key);
  }, [controller, key, url]);
  const stop = useCallback(() => controller.stop(), [controller]);
  // 身份变化的那一次render就隐藏旧内容，不等effect运行才清空。
  const state: AnswerState = envelope.scope === key && key !== null ? envelope.state : { status: "idle" };
  return { state, start, stop };
}
// #endregion stream-hook

// #region query-hook
export function useAsyncData<T>(identity: QueryIdentity | null, question: string, asOf: string,
  load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<QueryState<T>>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const controller = useMemo(() => new LatestQuery<T>(setState), []);
  const key = identity === null ? null : searchKey(identity, question, asOf);
  useEffect(() => {
    if (key === null) controller.cancel();
    else void controller.run(key, signal => loadRef.current(signal));
    return () => controller.cancel(false);
  }, [controller, key, attempt]);
  const visible: QueryState<T> = key !== null && state.status !== "idle" && state.key === key
    ? state : { status: "idle" };
  return { state: visible, retry: () => setAttempt(n => n + 1) };
}
// #endregion query-hook
