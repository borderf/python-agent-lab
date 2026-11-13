# TypeScript 核心示例工程

本目录是教材累计实现的唯一代码来源。第6、8–12章直接展示这里的源码；不要把各节独立观察片段拼成另一个App。环境基线为Node 22、pnpm 10.11.0、TypeScript 5.9.3，其他实际依赖锁在pnpm-lock.yaml。

## 命令

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
pnpm test
pnpm start
pnpm serve
```

typecheck检查真实依赖的类型；test先构建，再运行Node测试。start只是早期核心冒烟，不代表所有框架验收；最终以test逐项结果为准。

`pnpm serve`启动 `src/server.ts` 的 BFF Node HTTP 入口（默认 `127.0.0.1:8787`），同时托管 React 搜索页与来源摘要面板。`DOCPILOT_URL` 指向 Python 服务；开发 token `demo` 由 BFF 映射为 Python 教学身份，不是生产登录。来源面板目前只展示检索命中的引文，不会重新请求完整原文；独立来源页仍需补齐。

当前宿主构建脚本使用仓库根目录的 esbuild；首次从根目录运行 `npm ci`，再进入本目录执行以上 pnpm 命令。只安装本目录依赖尚不足以构建宿主。

模型协议演示使用独立配置，不能将 `DOCPILOT_URL` 改成模型地址：

```powershell
$env:DOCPILOT_URL = "http://127.0.0.1:8001"
$env:OLLAMA_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "你的本地模型标签"
# 只有模型代理要求认证时才配置 OLLAMA_API_KEY；不会复用 Python 教学 token。
pnpm serve
```

未配置模型时 `/api/answer` 返回 503，搜索仍可使用。此端点只演示模型流式协议，不检索资料、不产生已核验引用。正常 stop 才发送 done；length、未知结束原因和提前 EOF 都按未完成处理。Node 入口逐块转发 SSE，下游断开会传播取消；这不等于证明真实模型已经停止计算或计费。

## 范围

| 章节 | 实现 | 验证 |
| --- | --- | --- |
| 1–5 | contracts/state/map-limit/api-model | 校验、状态、合法undefined及有界并发 |
| 6 | sse/stream-events/stream-client/provider-stream | 字节分块、三种换行、坏载荷、提前EOF、错误终止、取消剩余读取；Ollama NDJSON 离线适配 |
| 8–9 | query/hooks/search-page | React DOM+jsdom StrictMode，旧结果、换租户及退出 |
| 10 | stream-controller/hooks/answer-page | A迟到取消不清B缓冲，停止保留末尾、多引文 |
| 11 | transport/search-contract/bff/server | 真实Hono路由与Node HTTP入口，身份、输入、总预算、错误与取消分类；/api/answer 离线SSE+真实HTTP假上游 |
| 18 | host-client + host/index.html | React搜索宿主、来源面板、流式回答；esbuild打包；Playwright未接入 |
| 12 | documents | 真实SQLite WASM+Drizzle，日期、唯一约束、回滚、导出重开 |

Python的tests/test_typescript_contract.py和本工程读取同一组冻结HTTP夹具。夹具覆盖两份Python服务及emoji偏移；不是复制一份只由前端自己认可的假数据。

未覆盖：真实浏览器布局/读屏、Playwright、真实模型流、生产Cookie认证、PostgreSQL、Docker及公网部署。jsdom不是浏览器端到端，SQLite WASM不是PostgreSQL。第13–18章相应任务须另留实际证据。数据库专项不与Python主线业务库双写。

## 先学哪份代码

正文的源码导入片段与本目录自动保持一致。独立观察、累计文件、设计示意、故意失败应按导读区分。先读当章机制，再修改对应文件，使用新输入验收；不另建第二套抄写项目。

test使用Node内置测试运行器，避免学习测试思想之前同时配置多个工具。第15章的Vitest属于迁移练习，迁移时保留同一输入/预期。CI会在Node 22按锁安装并运行本工程，源码、夹具或TS正文变化都会触发检查。
