import { isRecord } from "./contracts.js";

export type SearchHit = {
  sourceId: string; version: string; title: string; quote: string;
  location: { kind: "chunk"; chunkId: string; start: number; end: number }
    | { kind: "source"; section: string };
};

function requiredText(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${field}必须为非空文本`);
  return value;
}

function requiredOffsets(quote: string, start: unknown, end: unknown): { start: number; end: number } {
  if (typeof start !== "number" || !Number.isSafeInteger(start) || start < 0
      || typeof end !== "number" || !Number.isSafeInteger(end) || end <= start
      || end - start !== Array.from(quote).length) throw new Error("片段偏移不合法");
  return { start, end };
}

// 浏览器收到的 BFF 响应仍是外部输入；不能用 as 跳过运行时就校验。
export function parseSearchHits(value: unknown): SearchHit[] {
  if (!isRecord(value) || !Array.isArray(value.items)) throw new Error("search.items必须为数组");
  return Array.from(value.items, (raw: unknown) => {
    if (!isRecord(raw) || !isRecord(raw.location)) throw new Error("命中或location必须是对象");
    const common = {
      sourceId: requiredText(raw.sourceId, "sourceId"), version: requiredText(raw.version, "version"),
      title: requiredText(raw.title, "title"), quote: requiredText(raw.quote, "quote"),
    };
    if (raw.location.kind === "source") {
      return { ...common, location: { kind: "source" as const,
        section: requiredText(raw.location.section, "location.section") } };
    }
    if (raw.location.kind === "chunk") {
      return { ...common, location: { kind: "chunk" as const,
        chunkId: requiredText(raw.location.chunkId, "location.chunkId"),
        ...requiredOffsets(common.quote, raw.location.start, raw.location.end) } };
    }
    throw new Error("location.kind不合法");
  });
}

export function parseSearchResponse(value: unknown, mode: "core" | "persistent"): { items: SearchHit[] } {
  if (!isRecord(value) || !Array.isArray(value.items)) throw new Error("search.items必须为数组");
  const text = (row: Record<string, unknown>, key: string) => requiredText(row[key], key);
  return { items: Array.from(value.items, (raw: unknown) => {
    if (!isRecord(raw)) throw new Error("命中必须是对象");
    const common = { sourceId: text(raw, "source_id"), version: text(raw, "version"),
      title: text(raw, "title"), quote: text(raw, "text") };
    if (mode === "persistent") return { ...common,
      location: { kind: "source" as const, section: text(raw, "section") } };
    return { ...common, location: { kind: "chunk" as const, chunkId: text(raw, "chunk_id"),
      ...requiredOffsets(common.quote, raw.start, raw.end) } };
  }) };
}
