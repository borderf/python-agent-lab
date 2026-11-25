import { isRecord } from "./contracts.js";
import type { StreamEvent } from "./stream-state.js";

// 当前协议只实现 token/citation/done/error；tool/tool_result 是教材第14章的扩展目标。
export function parseStreamEvent(eventName: string, data: string): StreamEvent | null {
  // 可扩展协议：忽略未知事件名，但已知事件的坏载荷必须拒绝。
  if (!["token", "citation", "done", "error"].includes(eventName)) return null;
  const value: unknown = JSON.parse(data);
  if (!isRecord(value)) throw new Error("事件 data 必须是对象");
  const record = value;
  if (eventName === "token" && typeof record.text === "string") {
    return { type: "token", text: record.text };
  }
  if (eventName === "citation") {
    const citation = record.citation;
    if (isRecord(citation)
        && typeof citation.sourceId === "string" && citation.sourceId.trim().length > 0
        && typeof citation.version === "string" && citation.version.trim().length > 0
        && typeof citation.quote === "string" && citation.quote.trim().length > 0) {
      const { sourceId, version, quote } = citation;
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
  throw new Error(`事件 ${eventName} 的载荷不合法`);
}
