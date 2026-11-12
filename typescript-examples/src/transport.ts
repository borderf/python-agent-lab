export class RequestCancelled extends Error {
  constructor() { super("客户端已取消"); this.name = "AbortError"; }
}
type FailureStatus = 401 | 403 | 404 | 422 | 429 | 502 | 504;
export class UpstreamFailure extends Error {
  constructor(readonly status: FailureStatus, readonly code: string, message: string) { super(message); }
}
export type SearchBody = { question: string; as_of: string };
export function parseSearchBody(value: unknown): SearchBody {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new UpstreamFailure(422, "invalid_input", "请求体必须是对象");
  }
  const row = value as Record<string, unknown>;
  if (Object.keys(row).sort().join(",") !== "as_of,question" || typeof row.question !== "string") {
    throw new UpstreamFailure(422, "invalid_input", "只允许question/as_of");
  }
  const question = row.question.trim();
  const size = Array.from(question).length;
  if (size < 2 || size > 1000 || typeof row.as_of !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(row.as_of)) {
    throw new UpstreamFailure(422, "invalid_input", "问题或日期格式不合法");
  }
  const time = new Date(`${row.as_of}T00:00:00Z`);
  if (Number.isNaN(time.valueOf()) || time.toISOString().slice(0, 10) !== row.as_of) {
    throw new UpstreamFailure(422, "invalid_input", "日期不存在");
  }
  return { question, as_of: row.as_of };
}

export async function forwardSearch(upstreamUrl: string, upstreamToken: string, body: SearchBody,
  clientSignal: AbortSignal, fetcher: typeof fetch = fetch, timeoutMs = 15_000): Promise<unknown> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new RangeError("timeoutMs必须为正数");
  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), timeoutMs);
  const signal = AbortSignal.any([clientSignal, deadline.signal]);
  try {
    signal.throwIfAborted();
    const response = await fetcher(`${upstreamUrl}/api/search`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${upstreamToken}` },
      body: JSON.stringify(body), signal,
    });
    if (!response.ok) {
      await response.body?.cancel();
      const statuses: FailureStatus[] = [401, 403, 404, 422, 429];
      const status = statuses.find(n => n === response.status) ?? 502;
      throw new UpstreamFailure(status, `upstream_${status}`, "上游请求失败");
    }
    const result: unknown = await response.json(); // 时限覆盖读取body，不只等待响应头。
    signal.throwIfAborted();
    return result;
  } catch (cause) {
    if (clientSignal.aborted) throw new RequestCancelled();
    if (deadline.signal.aborted) throw new UpstreamFailure(504, "upstream_timeout", "检索超时");
    if (cause instanceof UpstreamFailure) throw cause;
    throw new UpstreamFailure(502, "upstream_failure", "上游连接或响应不合法");
  } finally { clearTimeout(timer); }
}
