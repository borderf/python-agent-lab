import { createSseParser, readStream } from "./sse.js";
import { parseStreamEvent } from "./stream-events.js";
import type { StreamEvent } from "./stream-state.js";

export class StreamFailure extends Error {
  constructor(message: string, readonly retryable: boolean) { super(message); }
}

export async function streamAnswer(
  url: string, body: unknown, onEvent: (event: StreamEvent) => void,
  signal: AbortSignal, fetcher: typeof fetch = fetch,
): Promise<void> {
  const response = await fetcher(url, {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body), signal,
  });
  const contentType = response.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase();
  if (!response.ok || contentType !== "text/event-stream") {
    await response.body?.cancel();
    throw new StreamFailure(`流式响应不合法: HTTP ${response.status}`, false);
  }
  const state: { terminal: StreamEvent | null; ordinal: number; citations: number } = {
    terminal: null, ordinal: 0, citations: 0,
  };
  const parser = createSseParser(({ event, data }) => {
    state.ordinal += 1;
    let parsed;
    try { parsed = parseStreamEvent(event, data); }
    catch (cause) { throw new Error(`第${state.ordinal}个SSE事件不合法`, { cause }); }
    if (parsed === null) return;
    if (parsed.type === "citation") state.citations += 1;
    if (parsed.type === "done" && !parsed.needsReview && state.citations === 0) {
      throw new StreamFailure("无引用的回答必须待复核", false);
    }
    if (parsed.type === "done" || parsed.type === "error") state.terminal = parsed;
    onEvent(parsed);
  });
  await readStream(response, line => {
    signal.throwIfAborted();
    parser(line);
    return state.terminal === null;
  });
  if (!state.terminal) throw new StreamFailure("流在done/error之前结束", true);
  if (state.terminal.type === "error") {
    throw new StreamFailure(state.terminal.message, state.terminal.retryable);
  }
}
