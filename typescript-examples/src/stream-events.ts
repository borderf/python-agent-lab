import type { Citation, StreamEvent } from "./stream-state.js";

export function parseStreamEvent(eventName: string, data: string): StreamEvent | null {
  // 可扩展协议：忽略未知事件名，但已知事件的坏载荷必须拒绝。
  if (!["token", "citation", "done", "error"].includes(eventName)) return null;
  const value: unknown = JSON.parse(data);
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("事件 data 必须是对象");
  }
  const record = value as Record<string, unknown>;
  if (eventName === "token" && typeof record.text === "string") {
    return { type: "token", text: record.text };
  }
  if (eventName === "citation") {
    const citation = record.citation;
    if (typeof citation === "object" && citation !== null && !Array.isArray(citation)
        && typeof (citation as Citation).sourceId === "string"
        && (citation as Citation).sourceId.trim().length > 0
        && typeof (citation as Citation).version === "string"
        && (citation as Citation).version.trim().length > 0
        && typeof (citation as Citation).quote === "string" && (citation as Citation).quote.trim().length > 0) {
      const { sourceId, version, quote } = citation as Citation;
      return { type: "citation", citation: { sourceId, version, quote } };
    }
  }
  if (eventName === "done" && typeof record.answerId === "string" && record.answerId.trim()
      && typeof record.needsReview === "boolean") {
    return { type: "done", answerId: record.answerId, needsReview: record.needsReview };
  }
  if (eventName === "error" && typeof record.message === "string" && record.message.trim()
      && typeof record.retryable === "boolean") {
    return { type: "error", message: record.message, retryable: record.retryable };
  }
  throw new Error(`未知事件 ${eventName}`);
}
