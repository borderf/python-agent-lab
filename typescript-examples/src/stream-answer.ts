import { OllamaStreamAdapter, type ProviderEvent } from "./provider-stream.js";
import { RequestCancelled, UpstreamFailure } from "./transport.js";

export type AnswerBody = { question: string };
export type OllamaConfig = { upstreamUrl: string; model: string; apiKey?: string };

export function parseAnswerBody(value: unknown): AnswerBody {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new UpstreamFailure(422, "invalid_input", "请求体必须是对象");
  }
  const row = value as Record<string, unknown>;
  if (Object.keys(row).sort().join(",") !== "question" || typeof row.question !== "string") {
    throw new UpstreamFailure(422, "invalid_input", "只允许question");
  }
  const question = row.question.trim();
  if (Array.from(question).length < 2 || Array.from(question).length > 1000) {
    throw new UpstreamFailure(422, "invalid_input", "问题长度必须为2到1000");
  }
  return { question };
}

export function providerEventToSse(event: ProviderEvent, answerId = "ollama-answer"): string {
  if (event.type === "token") return `event: token\ndata: ${JSON.stringify({ text: event.text })}\n\n`;
  if (event.type === "error") return `event: error\ndata: ${JSON.stringify({
    message: event.message, retryable: event.retryable })}\n\n`;
  if (event.type === "tool-call") return `event: tool\ndata: ${JSON.stringify({
    type: "tool-call", callId: event.callId, name: event.name, arguments: event.arguments })}\n\n`;
  if (event.reason !== "stop") return `event: error\ndata: ${JSON.stringify({
    message: event.reason === "length" ? "模型达到输出上限，回答未完成" : "模型结束原因不明确",
    retryable: false })}\n\n`;
  return `event: done\ndata: ${JSON.stringify({ answerId, needsReview: true,
    finishReason: event.reason, ...(event.usage ? { usage: event.usage } : {}) })}\n\n`;
}

export async function streamOllama(config: OllamaConfig, body: AnswerBody,
  clientSignal: AbortSignal, emit: (event: ProviderEvent) => void,
  fetcher: typeof fetch = fetch, timeoutMs = 30_000): Promise<void> {
  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), timeoutMs);
  const signal = AbortSignal.any([clientSignal, deadline.signal]);
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    signal.throwIfAborted();
    const headers = new Headers({ "Content-Type": "application/json" });
    if (config.apiKey) headers.set("Authorization", `Bearer ${config.apiKey}`);
    const response = await fetcher(`${config.upstreamUrl.replace(/\/$/, "")}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ model: config.model,
        messages: [{ role: "user", content: body.question }], stream: true }),
      signal,
    });
    if (!response.ok) {
      await response.body?.cancel();
      throw new UpstreamFailure(502, "upstream_stream_rejected", "供应商拒绝了流式请求");
    }
    if (!response.body) throw new UpstreamFailure(502, "upstream_stream_empty", "供应商没有返回流");
    reader = response.body.getReader();
    const adapter = new OllamaStreamAdapter();
    let finished = false;
    while (!finished) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const event of adapter.push(value)) {
        signal.throwIfAborted();
        emit(event);
        if (event.type === "done" || event.type === "error") {
          finished = true;
          await reader.cancel().catch(() => undefined);
          break;
        }
      }
    }
    if (!finished) for (const event of adapter.finish()) {
      signal.throwIfAborted();
      emit(event);
      if (event.type === "done" || event.type === "error") { finished = true; break; }
    }
    signal.throwIfAborted();
    if (!finished) throw new UpstreamFailure(502, "upstream_truncated", "模型流在结束事件之前断开");
  } catch (cause) {
    if (clientSignal.aborted) throw new RequestCancelled();
    if (deadline.signal.aborted) throw new UpstreamFailure(504, "upstream_timeout", "模型流超时");
    throw cause;
  } finally {
    clearTimeout(timer);
    if (reader) {
      await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }
}
