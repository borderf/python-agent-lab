export type ProviderUsage = { inputTokens?: number; outputTokens?: number };
export type ProviderEvent =
  | { type: "token"; text: string }
  | { type: "tool-call"; callId: string; name: string; arguments: unknown }
  | { type: "done"; reason: "stop" | "length" | "unknown"; usage?: ProviderUsage }
  | { type: "error"; message: string; retryable: boolean };

export class NdjsonDecoder {
  private decoder = new TextDecoder("utf-8", { fatal: true });
  private buffer = "";

  push(chunk: Uint8Array): string[] {
    this.buffer += this.decoder.decode(chunk, { stream: true });
    const lines = this.buffer.split(/\r?\n/);
    this.buffer = lines.pop() ?? "";
    if (this.buffer.length > 1_048_576 || lines.some(line => line.length > 1_048_576)) {
      throw new Error("Ollama 单行超过教学缓冲上限");
    }
    return lines.map(line => line.trim()).filter(line => line.length > 0);
  }

  finish(): string[] {
    this.buffer += this.decoder.decode();
    const rest = this.buffer.trim();
    this.buffer = "";
    return rest ? [rest] : [];
  }
}

export class OllamaStreamAdapter {
  private lines = new NdjsonDecoder();
  private callIndex = 0;

  push(chunk: Uint8Array): ProviderEvent[] {
    return this.lines.push(chunk).flatMap(line => this.mapLine(line));
  }

  finish(): ProviderEvent[] {
    return this.lines.finish().flatMap(line => this.mapLine(line));
  }

  private mapLine(line: string): ProviderEvent[] {
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      throw new Error("Ollama 事件不是合法 JSON");
    }
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new Error("Ollama 事件必须是对象");
    }
    const record = value as Record<string, unknown>;
    if (typeof record.error === "string" && record.error.trim()) {
      return [{ type: "error", message: record.error, retryable: false }];
    }
    const events: ProviderEvent[] = [];
    const message = record.message;
    if (typeof message === "object" && message !== null && !Array.isArray(message)) {
      const body = message as Record<string, unknown>;
      if (typeof body.content === "string" && body.content.length > 0) {
        events.push({ type: "token", text: body.content });
      }
      if (Array.isArray(body.tool_calls)) {
        for (const raw of body.tool_calls) {
          if (typeof raw !== "object" || raw === null || Array.isArray(raw)) continue;
          const call = raw as Record<string, unknown>;
          const fn = call.function;
          if (typeof fn !== "object" || fn === null || Array.isArray(fn)) continue;
          const functionRecord = fn as Record<string, unknown>;
          if (typeof functionRecord.name !== "string" || !functionRecord.name.trim()) continue;
          const callId = typeof call.id === "string" && call.id.trim()
            ? call.id
            : `ollama-call-${++this.callIndex}`;
          events.push({ type: "tool-call", callId, name: functionRecord.name,
            arguments: functionRecord.arguments ?? {} });
        }
      }
    }
    if (record.done === true) {
      const usage: ProviderUsage = {};
      if (typeof record.prompt_eval_count === "number") usage.inputTokens = record.prompt_eval_count;
      if (typeof record.eval_count === "number") usage.outputTokens = record.eval_count;
      const reason = record.done_reason === "length" ? "length"
        : record.done_reason === "stop" ? "stop" : "unknown";
      events.push({ type: "done", reason,
        ...(Object.keys(usage).length ? { usage } : {}) });
    }
    return events;
  }
}
