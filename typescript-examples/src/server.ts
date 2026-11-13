import { createServer, type IncomingHttpHeaders } from "node:http";
import { readFile } from "node:fs/promises";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { createBff } from "./bff.js";

const hostRoot = new URL("../host/", import.meta.url);
const staticFiles = new Map([
  ["/", { file: "index.html", type: "text/html; charset=utf-8" }],
  ["/app.js", { file: "app.js", type: "text/javascript; charset=utf-8" }],
]);

type Bff = ReturnType<typeof createBff>;

export function buildBff(env: NodeJS.ProcessEnv = process.env): Bff {
  const upstreamUrl = env.DOCPILOT_URL ?? "http://127.0.0.1:8000";
  const mode = env.DOCPILOT_MODE === "persistent" ? "persistent" : "core";
  const timeoutMs = Number(env.BFF_TIMEOUT_MS ?? "15000");
  const ollama = env.OLLAMA_URL && env.OLLAMA_MODEL
    ? { upstreamUrl: env.OLLAMA_URL, model: env.OLLAMA_MODEL,
        ...(env.OLLAMA_API_KEY ? { apiKey: env.OLLAMA_API_KEY } : {}) }
    : undefined;
  return createBff({
    upstreamUrl,
    mode,
    timeoutMs,
    ...(ollama ? { ollama } : {}),
    // 仅开发入口：浏览器用 Bearer demo，BFF 换成 Python 认可的教学 token。
    authenticate: async token => token === "demo"
      ? { tenantId: env.DEV_TENANT ?? "a", upstreamToken: env.DEV_UPSTREAM_TOKEN ?? "demo-a" }
      : null,
  });
}

function headersFrom(raw: IncomingHttpHeaders): Headers {
  const headers = new Headers();
  for (const [name, value] of Object.entries(raw)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) for (const item of value) headers.append(name, item);
    else headers.set(name, value);
  }
  return headers;
}

export function createBffServer(options: { app?: Bff } = {}) {
  const app = options.app ?? buildBff();
  return createServer(async (req, res) => {
    const disconnect = new AbortController();
    const abort = () => disconnect.abort();
    const onClose = () => { if (!res.writableFinished) abort(); };
    req.once("aborted", abort);
    res.once("close", onClose);
    try {
      const method = req.method ?? "GET";
      const pathname = new URL(req.url ?? "/", "http://localhost").pathname;
      const asset = method === "GET" ? staticFiles.get(pathname) : undefined;
      if (asset) {
        try {
          const body = await readFile(new URL(asset.file, hostRoot));
          res.writeHead(200, { "Content-Type": asset.type, "Cache-Control": "no-store" });
          res.end(body);
        } catch {
          res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
          res.end("宿主页尚未生成");
        }
        return;
      }
      const chunks: Buffer[] = [];
      for await (const chunk of req) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
      const hasBody = method !== "GET" && method !== "HEAD";
      const init: RequestInit = { method, headers: headersFrom(req.headers), signal: disconnect.signal };
      if (hasBody && chunks.length) init.body = new Uint8Array(Buffer.concat(chunks));
      const request = new Request(`http://${req.headers.host ?? "127.0.0.1"}${req.url ?? "/"}`, init);
      const response = await app.fetch(request);
      res.writeHead(response.status, Object.fromEntries(response.headers));
      // 先发响应头，再逐块转发；arrayBuffer()会把SSE退化成整包响应。
      res.flushHeaders();
      if (response.body && method !== "HEAD") {
        await pipeline(Readable.fromWeb(response.body as import("node:stream/web").ReadableStream<Uint8Array>), res);
      } else res.end();
    } catch {
      if (res.headersSent || res.destroyed) res.destroy();
      else {
        res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: { code: "internal", message: "BFF 服务暂不可用" } }));
      }
    } finally {
      req.off("aborted", abort);
      res.off("close", onClose);
    }
  });
}

if (process.argv[1]?.endsWith("server.js")) {
  const port = Number(process.env.BFF_PORT ?? "8787");
  createBffServer().listen(port, "127.0.0.1", () => {
    console.log(`BFF listening on http://127.0.0.1:${port}`);
  });
}
