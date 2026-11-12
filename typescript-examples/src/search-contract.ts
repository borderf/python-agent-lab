export type SearchHit = {
  sourceId: string; version: string; title: string; quote: string;
  location: { kind: "chunk"; chunkId: string; start: number; end: number }
    | { kind: "source"; section: string };
};
export function parseSearchResponse(value: unknown, mode: "core" | "persistent"): { items: SearchHit[] } {
  if (typeof value !== "object" || value === null || !("items" in value) || !Array.isArray(value.items)) {
    throw new Error("search.items必须为数组");
  }
  return { items: value.items.map((raw: unknown) => {
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) throw new Error("命中必须是对象");
    const row = raw as Record<string, unknown>;
    const text = (key: string) => {
      const result = row[key];
      if (typeof result !== "string" || !result.trim()) throw new Error(`${key}必须为非空文本`);
      return result;
    };
    const common = { sourceId: text("source_id"), version: text("version"), title: text("title"), quote: text("text") };
    if (mode === "persistent") return { ...common, location: { kind: "source" as const, section: text("section") } };
    const start = row.start, end = row.end;
    if (typeof start !== "number" || !Number.isSafeInteger(start) || start < 0
        || typeof end !== "number" || !Number.isSafeInteger(end) || end <= start
        || end - start !== Array.from(common.quote).length) throw new Error("片段偏移不合法");
    return { ...common, location: { kind: "chunk" as const, chunkId: text("chunk_id"), start, end } };
  }) };
}
