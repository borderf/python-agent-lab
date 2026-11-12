# TypeScript 核心示例工程

本目录是教材累计实现的唯一代码来源。第6、8–12章直接展示这里的源码；不要把各节独立观察片段拼成另一个App。环境基线为Node 22、pnpm 10.11.0、TypeScript 5.9.3，其他实际依赖锁在pnpm-lock.yaml。

## 命令

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
pnpm test
pnpm start
```

typecheck检查真实依赖的类型；test先构建，再运行Node测试。start只是早期核心冒烟，不代表所有框架验收；最终以test逐项结果为准。

## 范围

| 章节 | 实现 | 验证 |
| --- | --- | --- |
| 1–5 | contracts/state/map-limit/api-model | 校验、状态、合法undefined及有界并发 |
| 6 | sse/stream-events/stream-client | 字节分块、三种换行、坏载荷、提前EOF、错误终止、取消剩余读取 |
| 8–9 | query/hooks/search-page | React DOM+jsdom StrictMode，旧结果、换租户及退出 |
| 10 | stream-controller/hooks/answer-page | A迟到取消不清B缓冲，停止保留末尾、多引文 |
| 11 | transport/search-contract/bff | 真实Hono路由，身份、输入、总预算、错误与取消分类 |
| 12 | documents | 真实SQLite WASM+Drizzle，日期、唯一约束、回滚、导出重开 |

Python的tests/test_typescript_contract.py和本工程读取同一组冻结HTTP夹具。夹具覆盖两份Python服务及emoji偏移；不是复制一份只由前端自己认可的假数据。

未覆盖：真实浏览器布局/读屏、Playwright、真实模型流、生产Cookie认证、PostgreSQL、Docker及公网部署。jsdom不是浏览器端到端，SQLite WASM不是PostgreSQL。第13–18章相应任务须另留实际证据。数据库专项不与Python主线业务库双写。

## 先学哪份代码

正文的源码导入片段与本目录自动保持一致。独立观察、累计文件、设计示意、故意失败应按导读区分。先读当章机制，再修改对应文件，使用新输入验收；不另建第二套抄写项目。

test使用Node内置测试运行器，避免学习测试思想之前同时配置多个工具。第15章的Vitest属于迁移练习，迁移时保留同一输入/预期。CI会在Node 22按锁安装并运行本工程，源码、夹具或TS正文变化都会触发检查。
