export type Citation = {
  sourceId: string;
  quote: string;
};

export type Answer = {
  answer: string;
  citations: Citation[];
  needsReview: boolean;
};

export type Result<T, E> =
  | { ok: true; value: T }
  | { ok: false; error: E };

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isCitation(value: unknown): value is Citation {
  return (
    isRecord(value) &&
    typeof value.sourceId === "string" &&
    value.sourceId.trim().length > 0 &&
    typeof value.quote === "string" &&
    value.quote.trim().length > 0
  );
}

export function parseAnswer(value: unknown): Result<Answer, string> {
  if (!isRecord(value)) return { ok: false, error: "回答必须是对象" };
  const { answer, citations, needsReview } = value;
  if (typeof answer !== "string" || !answer.trim()) {
    return { ok: false, error: "answer 不能为空" };
  }
  if (!Array.isArray(citations) || !Array.from(citations).every(isCitation)) {
    return { ok: false, error: "citations 格式不合法" };
  }
  if (typeof needsReview !== "boolean") {
    return { ok: false, error: "needsReview 必须是布尔值" };
  }
  if (citations.length === 0 && !needsReview) {
    return { ok: false, error: "没有引用时必须标记待复核" };
  }
  return {
    ok: true,
    value: {
      answer,
      citations: citations.map((item) => ({ sourceId: item.sourceId, quote: item.quote })),
      needsReview,
    },
  };
}
