# 附录C　Java 后端转 TypeScript 全栈路线

[全书目录](教材目录.md) · [导读](00-导读与学习方法.md) · [与 Python 后端的契约](附录B-与Python后端的契约.md)

这份路线回答一个问题：**已有 Java/Spring 后端经验，怎样在最短路径上达到“能用 TypeScript 独立交付全栈 AI 应用”**。不是把 Java 的分层、注解和 ORM 原样搬过来，而是保留工程判断，替换语言与运行时的心智模型。

## 一、先选一条技术栈，不要同时学四套

建议主线：

```text
React + Vite + TypeScript      浏览器界面
Hono + TypeScript              Node BFF（认证、转发、流式）
SQLite → PostgreSQL            本地到部署
Drizzle ORM + SQL              数据访问
OpenAI-compatible SDK / fetch  模型调用
Vitest + Playwright            测试
```

选择理由：

- **React + Vite**：先把组件、状态和异步数据学清楚，不被 Next.js 的 Server Components、缓存和路由约定淹没。
- **Hono**：基于 Web `Request/Response`，与 `fetch`、SSE、边缘部署一致，类型推导直接；比 NestJS 轻，适合先理解 BFF 边界。
- **Drizzle + SQL**：对 Java 后端更友好，能看到 SQL 和事务；Prisma 可以作为替代，不建议两套同时学。
- **不把 RAG 写在 TypeScript**：检索、权限、引用和评测继续用 Python 教材的 DocPilot；TS 只做 BFF、界面和流式消费。
- **Next.js 作为可选迁移**：第 18 章后用附录或小项目补 Server Components/Route Handlers；企业若用 NestJS，按 Spring 的 DI/模块/拦截器类比，不必从零再学一套思想。

## 二、18 章组织（4 个部分，一条项目线）

| 部分 | 章节 | 交付物 |
| --- | --- | --- |
| 0 迁移 | 0. Java 后端到 TypeScript：心智模型与工具链 | 一个能跑 `tsc --noEmit`、Vitest 和 pnpm 的最小仓库 |
| 1 类型、异步与流式 | 1–4 类型/校验；5 异步/取消；6 HTTP/SSE | DocPilot API 类型、Zod 校验、流式客户端 |
| 2 工程化与界面 | 7 模块/构建；8 React 组件；9 异步数据；10 流式界面 | 搜索页、回答页、引用与待复核、流式渲染 |
| 3 BFF、数据与 AI | 11 Hono BFF；12 SQL/Drizzle；13 认证/多租户；14 AI SDK/工具/MCP | 可登录、可持久化、可调用模型的 BFF |
| 4 测试与交付 | 15 Vitest；16 Playwright；17 观测/成本/安全；18 部署与 Capstone | 可部署、可演示、可答辩的 DocPilot Console |

每章固定产出：可运行代码、失败案例、测试或验收记录、一段能讲清的取舍。第 18 章不再加新概念，只把前 17 章的切片接起来。

## 三、Java 与 TypeScript 的关键对照

| Java/Spring | TypeScript/Node | 迁移时要注意 |
| --- | --- | --- |
| `interface` 名义类型，`implements` 显式 | 结构化类型，形状匹配即可 | 不要以为“形状像”就业务正确；运行时仍要校验 |
| 泛型擦除 | 类型也擦除，且只在编译期 | 两边都不能靠泛型做运行时判断；TS 连 `T.class` 都没有 |
| `Optional<T>` | `T \| undefined` / `T \| null` | 可选属性、缺字段、显式空值是三种状态 |
| Bean Validation 注解 | Zod/手写 schema | 注解在运行时由框架执行；TS 类型不执行 |
| Spring MVC 控制器 | Hono/Fastify 路由或 Next Route Handler | 参数解析、错误映射、中间件要自己组合 |
| `@Transactional` | 数据库事务 API | 事务边界仍要自己画；不要假设 ORM 自动包一切 |
| JPA/Hibernate | Drizzle/Prisma + SQL | 先写 SQL 和迁移，再选 ORM；关系加载要显式 |
| `ExecutorService`/线程池 | 事件循环 + Promise | 阻塞调用会卡住整个 loop；CPU 工作放 Worker |
| `CompletableFuture` | `Promise`/`async` | 取消是协作的；Promise 本身不可取消 |
| Maven/Gradle | pnpm + `package.json`/lockfile | lockfile 必须提交；依赖版本要可复现 |
| JUnit/MockMvc | Vitest/supertest/Playwright | 单测、契约、端到端分层，不靠一个工具全包 |
| `application.yml` | 环境变量 + 配置模块 | 密钥不进前端；启动时校验配置 |
| checked exception | `throw`/`Result` | TS 没有 checked exception；错误类型要自己建模 |

## 四、按阶段学习（建议 10–12 周，按实际调整）

### 阶段 1：类型与运行时（第 1–4 章，约 2 周）

- 把 Java 的 DTO/枚举/校验器改写成 TS 类型 + Zod；
- 写 `Result<T,E>`、错误分类和字段路径；
- 每天一个 20 行类型练习，必须跑 `tsc --noEmit`；
- 交付：DocPilot 的 `SearchHit`、`Answer`、`ApiError` 类型与校验。

### 阶段 2：异步、SSE 与工程化（第 5–7 章，约 2 周）

- 建 pnpm 仓库、`tsconfig`、ESM、Vitest；
- 用 `fetch` + `AbortController` 写 API 客户端；
- 把 SSE 解析拆成纯函数并写跨 chunk 测试；
- 交付：命令行版 DocPilot 客户端，能流式打印并中止。

### 阶段 3：React 界面（第 8–10 章，约 2 周）

- 组件、props、状态提升、表单；
- 用判别联合表示 `loading/streaming/done/error`；
- 引用列表、来源打开、待复核提示；
- 交付：搜索页 + 回答页 + 流式渲染，键盘可操作。

### 阶段 4：BFF 与数据（第 11–13 章，约 2–3 周）

- Hono 路由、中间件、错误映射、配置校验；
- SQLite 建表/迁移/事务；Drizzle 查询；
- 会话/令牌、租户隔离、权限测试；
- 交付：登录、上传资料、查询历史、重启后仍在。

### 阶段 5：AI 集成与恢复（第 14 章 + Python 第 24–25 章，约 2 周）

- 模型调用、流式转发、工具调用参数校验；
- 审批/恢复的 BFF 接口；不把模型密钥放浏览器；
- 交付：一次工具调用 + 一次人工审批 + 一次断线重连。

### 阶段 6：测试、部署与答辩（第 15–18 章，约 2 周）

- Vitest 单测/契约、Playwright 一条主路径；
- 日志、请求 ID、成本、错误率；
- Docker/环境变量/CI/回滚；
- 交付：可复现部署 + 5 分钟演示 + 失败复盘。

## 五、哪些内容不要先学

- **不要同时学 Next.js、NestJS、Prisma、GraphQL、tRPC**。先把 React + Hono + SQL 走通，再按岗位选一个。
- **不要先深挖条件类型/映射类型**。能读库的类型声明、能写泛型约束即可；类型体操留到需要写库时。
- **不要在 TypeScript 里重写 RAG**。检索、权限、引用、评测用 Python 服务；TS 负责契约、界面和流。
- **不要用 `any` 快速移植 Java 代码**。先写 `unknown` + 校验，再逐步收窄；`any` 会把迁移问题推迟到运行时。
- **不要把 TypeScript 类型当 Bean Validation**。类型在编译后消失；外部输入必须运行时校验。

## 六、与现有六章的关系

当前第 1–18 章已完成：类型/异步/SSE（1–6）、工程化/React/流式界面（7–10）、Hono BFF/SQL/认证/AI 工具（11–14）、测试/观测/部署（15–18）。下一步不是继续加章节，而是按阶段做一次真实交付：

1. **用新数据走通**：换一份制度材料，从导入、检索、流式回答到引用核对；
2. **制造失败**：401/403/404/422/429/504、断流、跨租户、重复审批，各留一条记录；
3. **补真实模型/部署**：按第 14、17、18 章接入模型、指标和容器，不用替身冒充完成。

## 七、验收标准

能独立完成下面这条链，才算“熟练”而不是“看过”：

```text
输入问题 → 前端校验 → BFF 认证/转发 → Python 检索/模型
→ SSE 流式返回 → 引用与待复核渲染 → 错误/取消/重试
→ 审批写入 → 重启后恢复 → 测试/日志/部署
```

每一段都要有：正常输入、一个坏输入、一个取消或超时、一个失败恢复记录。只演示成功路径，不算完成。

[全书目录](教材目录.md) · [附录B](附录B-与Python后端的契约.md)