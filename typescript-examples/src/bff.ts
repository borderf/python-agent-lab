import { Hono } from "hono";
import { RequestCancelled, UpstreamFailure, forwardSearch, parseSearchBody } from "./transport.js";
import { parseSearchResponse } from "./search-contract.js";

type Actor = { tenantId: string; upstreamToken: string };
type Env = { Variables: { requestId: string; actor: Actor } };
export function createBff(options: {
  upstreamUrl: string; mode: "core" | "persistent";
  authenticate: (token: string) => Promise<Actor | null>;
  fetcher?: typeof fetch; timeoutMs?: number;
}) {
  const app = new Hono<Env>();
  app.use("*", async (c, next) => {
    c.set("requestId", crypto.randomUUID());
    c.header("X-Request-ID", c.get("requestId"));
    await next();
  });
  app.get("/health", c => c.json({ status: "ok" }));
  app.use("/api/*", async (c, next) => {
    const header = c.req.header("Authorization");
    const actor = header?.startsWith("Bearer ") ? await options.authenticate(header.slice(7).trim()) : null;
    if (!actor) throw new UpstreamFailure(401, "unauthorized", "需要有效身份");
    c.set("actor", actor);
    await next();
  });
  app.post("/api/search", async c => {
    let raw: unknown;
    try { raw = await c.req.json(); } catch { throw new UpstreamFailure(422, "invalid_json", "请求不是JSON"); }
    const body = parseSearchBody(raw);
    const result = await forwardSearch(options.upstreamUrl, c.get("actor").upstreamToken, body,
      c.req.raw.signal, options.fetcher, options.timeoutMs);
    try { return c.json(parseSearchResponse(result, options.mode)); }
    catch { throw new UpstreamFailure(502, "invalid_response", "上游字段与选定契约不一致"); }
  });
  app.onError((error, c) => {
    // 499仅作本地分类；真实连接断开后通常无法再把响应送给客户端。
    if (error instanceof RequestCancelled) return new Response(null, { status: 499 });
    const status = error instanceof UpstreamFailure ? error.status : 500;
    const code = error instanceof UpstreamFailure ? error.code : "internal";
    return c.json({ error: { code, message: error instanceof UpstreamFailure ? error.message : "服务暂不可用",
      requestId: c.get("requestId") } }, status);
  });
  return app;
}
