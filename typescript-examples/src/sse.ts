export type SseEvent = { event: string; data: string };

export function createSseParser(onEvent: (event: SseEvent) => void) {
  let eventName = "message";
  let dataLines: string[] = [];
  let size = 0;
  return (line: string): void => {
    if (line === "") {
      if (dataLines.length > 0) {
        onEvent({ event: eventName || "message", data: dataLines.join("\n") });
      }
      eventName = "message";
      dataLines = [];
      size = 0;
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") eventName = value;
    if (field === "data") {
      size += value.length + 1;
      if (size > 1_048_576) throw new Error("SSE事件超过教学上限");
      dataLines.push(value);
    }
  };
}

export async function readStream(response: Response, onLine: (line: string) => boolean | void): Promise<void> {
  if (!response.body) throw new Error("响应没有body");
  const reader = response.body.getReader();
  // 本客户端选择严格拒绝非法UTF-8，不冒充原生EventSource的完整实现。
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  function consume(final: boolean): boolean {
    while (true) {
      const at = buffer.search(/[\r\n]/);
      if (at < 0) return true;
      if (buffer[at] === "\r" && at === buffer.length - 1 && !final) return true;
      const width = buffer[at] === "\r" && buffer[at + 1] === "\n" ? 2 : 1;
      const line = buffer.slice(0, at);
      buffer = buffer.slice(at + width);
      if (onLine(line) === false) return false;
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        consume(true);
        return; // EOF不伪造空行；未分隔完成的事件丢弃。
      }
      buffer += decoder.decode(value, { stream: true });
      if (buffer.length > 1_048_576) throw new Error("SSE读取缓冲超过教学上限");
      if (!consume(false)) return;
    }
  } finally {
    try { await reader.cancel(); } catch { /* 不覆盖原始错误。 */ }
    reader.releaseLock();
  }
}
