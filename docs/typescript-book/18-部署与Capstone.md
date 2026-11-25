# 第18章　部署、回滚与 Capstone

[上一章](17-可观测性与成本安全.md) · [全书目录](教材目录.md)

## 1. 学习目标与前置知识

能把 TypeScript 全栈应用打成可复现的构建产物，用容器/环境变量/迁移/健康检查部署，设计回滚与兼容迁移；能按验收矩阵交付 DocPilot Console，而不是“本机能跑”。前置：第 7、11–17 章。

**本章从这里开始：** 本地 `pnpm dev` 正常，CI 构建失败；数据库迁移先删列，旧实例还在写；发布后健康检查通过，但用户搜索全 500。部署不是“传上去”，是**构建、迁移、启动、验证、回滚**一整套可重复流程。

**当前起点：** 配套工程已有 esbuild 构建的 React 宿主页、Node 监听入口和流式协议演示；迁移脚本、生产会话、完整来源页与 Docker 交付仍未补齐。本章先复用现有入口，再给出生产构建与发布模板。模板中的 dist/client、dist/server 布局不同于当前 dist/ 与 host/，需要完成相应改造后才能构建镜像。不要用 pnpm start 的离线脚本代替 pnpm serve。

## 2. 基础知识讲解

### 2.1 构建产物与运行环境

先按[配套工程说明](../../typescript-examples/README.md)准备根目录与子工程依赖，再在 typescript-examples 中执行：

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
pnpm serve
```

独立完成部署工程时，`vite build`只产出浏览器资源；BFF/服务端代码还需构建。下列是**待实现的配置设计**，相应依赖、入口与配置要一起建立并锁定，不直接覆盖配套工程现有脚本：

```json
{
  "scripts": {
    "build:client": "vite build",
    "build:server": "tsc -p tsconfig.server.json",
    "build": "pnpm build:client && pnpm build:server"
  }
}
```

`tsconfig.server.json` 设置 `outDir: "dist/server"`、`rootDir: "src/server"`、`module: "NodeNext"`；Vite 的 `outDir` 设为 `dist/client`。不要让 Docker 去猜 `.output` 或 `dist/server.js`，构建脚本和镜像路径必须一致。

### 2.2 沿已有宿主完成浏览器主路径

先阅读并修改已有文件，走通浏览器搜索 → BFF → Python → 结果与来源摘要，不另建平行的 apps/web 工程：

```text
typescript-examples/host/index.html
typescript-examples/src/host-client.tsx  挂载搜索与来源摘要
typescript-examples/src/server.ts       HTTP入口与逐块响应转发
typescript-examples/src/bff.ts          身份、校验、协议适配
```

继续改造时保留这些约束：

- 用 `textContent` 渲染用户/模型文本，不把返回内容拼进 `innerHTML`；
- 当前来源面板是命中引文预览；完整原文入口需经 BFF 请求 Python，重新授权并核对 source/version；
- 请求失败显示错误与重试，不显示空列表冒充“没有结果”。

当前可运行命令（执行目录为 typescript-examples，Python 启动步骤见切片手册）：

```powershell
pnpm build
pnpm serve
```

Playwright 尚未安装；自行接入后先用 page.route 固定结果验证交互，再增加真实 BFF + Python 冒烟。来源全文、正式会话与写审批分别扩展；已有 `/api/answer` 是独立模型协议演示，不能代替有证据的 RAG 回答。

当前实现、协议和浏览器待验项统一见[最小全栈切片](../project-practice/最小全栈切片.md)。本地 HTTP 测试通过与浏览器交互验收分别记录。

### 2.3 多阶段 Dockerfile

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist/client ./dist/client
COPY --from=build /app/dist/server ./dist/server
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
EXPOSE 8787
CMD ["node", "dist/server/server.js"]
```

真实项目要处理非 root 用户、只复制生产依赖、健康检查、时区/证书。镜像构建也应在 CI 完成并打 digest，部署用 digest 而不是 `latest`。

### 2.4 配置与密钥

```ts
function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`缺少环境变量 ${name}`);
  return value;
}

const port = Number(process.env.PORT ?? 8787);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new RangeError("PORT 必须是 1–65535 的整数");
}

export const config = {
  port,
  databaseUrl: required("DATABASE_URL"),
  docpilotUrl: required("DOCPILOT_URL"),
  sessionSecret: required("SESSION_SECRET"),
};
```

启动时失败优于运行时 `undefined`。示例在启动时检查端口为1–65535范围的整数，不能只用 `Number` 接受 NaN 或小数。密钥用平台 secret/环境变量注入，不进镜像、不进仓库、不进日志。不同环境用不同配置，但构建产物尽量一致。

### 2.5 健康检查

```ts
app.get("/health", (c) => c.json({ ok: true }));

app.get("/ready", async (c) => {
  const dbOk = await checkDatabase();
  const upstreamOk = await checkUpstream();
  return dbOk && upstreamOk
    ? c.json({ ok: true })
    : c.json({ ok: false }, 503);
});
```

`/health` 表示进程活着；`/ready` 表示能接流量（数据库/上游/迁移完成）。liveness 不应依赖外部上游，否则上游抖动会重启所有实例。

### 2.6 迁移与兼容发布

数据库迁移分“扩展/收缩”：

1. 加新列/新表（兼容旧代码）；
2. 双写/回填；
3. 切换读路径；
4. 旧实例退出后删旧列。

不要在发布同一刻执行破坏性迁移；回滚代码不会撤销已写数据。迁移脚本要版本化、可重复执行（幂等），并在预发环境跑过。

### 2.7 发布策略与回滚

- **滚动**：逐批替换，适合大多数；
- **蓝绿**：两套环境切换，回滚快，成本高；
- **金丝雀**：小流量验证指标，逐步放量；
- 回滚要能回到上一个镜像 digest + 兼容的数据库状态；准备“前滚修复”方案。

发布后检查：错误率、P95、TTFT、成本、关键业务成功率；指标异常先回滚，再定位。

### 2.8 当前产物与生产模板不要混用

| 项目 | 当前配套工程 | 本章生产模板 | 改造前不能声称 |
| --- | --- | --- | --- |
| 浏览器资源 | `host/index.html`、`host/app.js` | `dist/client` | Docker已包含当前宿主 |
| 服务端JS | `dist/server.js`及dist模块 | `dist/server/server.js` | 当前CMD能启动 |
| 构建命令 | tsc build + build-host | Vite client + server tsc | 同一构建脚本产出两种布局 |
| Web依赖 | Node原生`node:http` | 示例`@hono/node-server` | 当前依赖可直接跑模板 |
| 健康检查 | `/health` | `/health` + `/ready` | 当前已有依赖就绪检查 |
| 监听地址 | `127.0.0.1` | 容器需从容器外访问 | 当前端口已映射可用 |

`server.ts`只服务`/`和`/app.js`两个静态文件，并绑定127.0.0.1。Docker端口映射不能越过容器内回环地址；部署改造必须同时调整监听地址、静态产物路径和启动脚本。只把文件复制进镜像不会自动得到生产应用。

### 2.9 配置输入与启动失败边界

| 变量 | 当前读取者 | 当前行为 | 生产注意 |
| --- | --- | --- | --- |
| `BFF_PORT` | server入口 | 默认8787，Number转换 | 未做1–65535启动校验 |
| `DOCPILOT_URL` | buildBff | 默认本地8000 | 生产用内部服务地址 |
| `DOCPILOT_MODE` | buildBff | persistent或core | 必须与Python响应契约一致 |
| `BFF_TIMEOUT_MS` | buildBff→transport | 默认15000，forwardSearch校验正数 | NaN会到请求期失败，应启动期拒绝 |
| `OLLAMA_URL`/`OLLAMA_MODEL` | buildBff | 同时存在才配置模型 | 只配一个会被视为未配置 |
| `OLLAMA_API_KEY` | streamOllama | 作为供应商Bearer | 不进镜像/日志/前端 |
| `DEV_TENANT`/`DEV_UPSTREAM_TOKEN` | 教学authenticate | 固定demo浏览器身份 | 不得作为生产会话 |
| `DATABASE_URL`/`SESSION_SECRET` | 仅模板config | 当前server不读取 | 实现持久会话/迁移后再要求 |

启动配置应在进程接流量前验证并失败，而不是等用户请求后出现500。不同环境可注入不同值，但同一镜像 digest不变；秘密由平台secret注入，不写进Dockerfile或构建参数历史。

### 2.10 发布与回滚的状态矩阵

| 阶段 | 数据库状态 | 代码状态 | 回滚条件 |
| --- | --- | --- | --- |
| 扩展 | 新列可空/新表存在，旧代码不依赖 | 旧版+迁移job | 迁移失败则停止，不启动新版 |
| 双写/回填 | 新旧字段都写，校验一致性 | 新版 | 可回旧代码，旧字段仍完整 |
| 切读 | 新字段成为真相，仍保留旧写路径 | 新版 | 指标异常回旧镜像并读旧字段 |
| 收缩 | 旧实例退出、无旧读后删列 | 新版 | 通常只能前滚修复，不能恢复已删列 |

镜像回滚只恢复代码，不恢复数据库。每次发布记录commit、镜像digest、迁移版本和上一兼容digest；不能只记录可覆盖的latest tag。

## 3. 原理讲解与推导

### 3.1 不可变产物

同一份构建产物在测试/预发/生产运行，只换配置。不要在服务器上重新构建或改代码；“在我机器上能跑”无法复现。

### 3.2 数据库是发布中最难回滚的部分

代码可以切回旧镜像，数据迁移往往不可逆。先兼容、再切换、最后清理；删除列/表要等旧实例完全退出并确认无读。

### 3.3 验收矩阵

Capstone 不只演示成功路径，要给出：

| 维度 | 证据 |
| --- | --- |
| 功能 | 搜索/回答/引用/停止/审批主路径 |
| 失败 | 401/403/404/422/429/504 各一条 |
| 流式 | 首 token、完成、停止、断线 |
| 数据 | 重启后仍在、迁移、回滚 |
| 安全 | 跨租户 404、密钥不进前端、CSP |
| 质量 | 单测/集成/契约/E2E 结果 |
| 运维 | 日志/指标/追踪/告警截图 |
| 成本 | 一次请求 token/成本估算 |

### 3.4 回滚决策先看兼容性，再看新旧程度

```text
发布后指标异常
  → 失败来自代码还是迁移？
  → 当前数据库是否仍兼容上一镜像？
      是：切回上一digest，摘除/重启异常实例，复验health与主路径
      否：停止破坏性操作，前滚修复或从备份恢复，并记录数据影响
```

`/health`只证明进程响应；回滚后还要验证`/api/search`合法请求、错误码和一条关键浏览器路径。数据库已写入的新格式可能让旧代码报错，所以“镜像能启动”不是回滚成功。回滚过程本身也要有requestId/日志和固定digest记录。

## 4. 示例与逐步走查

```ts
// server.ts
import { serve } from "@hono/node-server";
import app from "./app.js";
import { config } from "./config.js";

serve({ fetch: app.fetch, port: config.port }, (info) => {
  console.log(JSON.stringify({ level: "info", event: "started", port: info.port }));
});
```

部署命令示例：

```powershell
$imageTag = "docpilot-console:$(git rev-parse --short HEAD)"
docker build -t $imageTag .
docker run --rm -p 8787:8787 `
  -e DATABASE_URL=... -e DOCPILOT_URL=... -e SESSION_SECRET=... `
  $imageTag
```

逐步检查：

1. 构建用lockfile，以commit SHA作便于识别的tag；tag可被覆盖，不是镜像digest。推送后记录仓库返回的sha256内容digest，部署与回滚再引用它；
2. 启动前跑迁移（单独 job/init container），失败阻止发布；
3. `/ready` 通过后再接流量；
4. 发布后看错误率/P95/TTFT；
5. 异常回滚到上一个 digest，确认数据库兼容。

### 4.1 当前命令实际产出什么

| 命令 | 实际行为 | 验证点 |
| --- | --- | --- |
| `pnpm typecheck` | tsc --noEmit | 类型与导入 |
| `pnpm test` | build后运行Node测试，含真实HTTP流 | 7个测试文件退出码 |
| `pnpm build` | 编译dist并生成host/app.js | dist/server.js与宿主资源存在 |
| `pnpm serve` | 启动Node BFF，默认127.0.0.1:8787 | `/health`、`/`、`/api/search` |
| `pnpm start` | 运行离线dist/main.js | 不是Web服务，不能用于部署验收 |

当前没有`/ready`、数据库迁移或Docker镜像。步骤3中的ready是模板目标；在实现前只能用现有health和真实搜索请求记录，不能勾选生产就绪。容器化后还要验证非root、只读文件系统、秘密注入和外部可达监听。

## 5. 练习

本节只计三项练习：练习一是5.1的Capstone交付；练习二由5.2与5.3两个步骤组成，完成容器与兼容迁移；练习三是5.4的完整演示。保留5.2–5.4原标题作为定位锚点，不把每个步骤另算一项。

### 5.1 Capstone：DocPilot Console

交付一个可运行的全栈切片：

下面是完整交付目标，当前回归只覆盖其中的状态、路由与数据库切片。逐项记录“现有基线、自己实现、真实环境验证”，不把整张目标表勾成已完成。Vitest迁移可选，已有Node测试可以继续使用；关键是保留相同失败案例。

- 登录/登出，HttpOnly 会话；
- 搜索制度，显示来源、版本、有效期；
- 提问，SSE 流式回答，引用可打开；
- 停止/失败保留部分文本；
- 一次写操作走审批，幂等执行；
- 重启后资料/会话/审批仍在；
- 测试：单测/集成/契约（Node或Vitest）+ Playwright主路径；
- 观测：requestId、错误率、P95、TTFT、成本；
- 部署：Docker/环境变量/迁移/回滚说明。

**演示脚本（5 分钟）：**

1. 未登录访问受保护页 → 401/跳转；
2. 登录，搜索“预付款”，打开引用；
3. 提问，展示流式、引用、停止；
4. 制造一次 504/断流，展示保留部分内容和重试；
5. 审批一次写操作，重复提交不重复执行；
6. 重启服务，查询仍在；
7. 展示测试/指标/成本面板；
8. 说明已知限制和下一步。

**验收原则：** 每个“完成”都要有命令、输出、失败案例和限制；不要用框架名代替证据。

### 5.2 跟写

**练习二，第一步：** 写多阶段 Dockerfile 和 `.dockerignore`。先按2.8改造产物布局和监听地址，再构建镜像并以非 root 运行；用 `/health` 做容器健康检查，`/ready`只有在实现依赖检查后才加入。记录镜像digest，不用latest作为验收证据。

### 5.3 改造

**练习二，第二步：** 设计一次兼容迁移：给 `documents` 加 `checksum` 列，双写/回填/切换读/旧实例退出后再删旧逻辑。分别写前进与回滚命令，并说明哪一步之后不能再回旧镜像。把第二步的迁移版本与第一步的digest放进同一发布记录。

### 5.4 独立

**练习三：** 按验收矩阵做一次完整演示，录屏/截图/命令记录；请另一人按 README 从干净环境启动，记录卡点。演示必须使用练习二记录的固定digest和迁移版本，并实际执行一次兼容回滚，不能只口头说明。

## 6. 验收与自测

先检查主路径，再检查边界，最后检查交付。每一步同时记录操作、预期和证据；没有实现的端点不能填“通过”。

| 操作 | 预期 | 证据 |
| --- | --- | --- |
| 登录后搜索、打开来源 | 结果/版本/引文可见 | 请求响应、requestId、浏览器截图 |
| 流式提问后停止 | 已收文本保留，状态stopped | SSE事件、页面状态、runner/服务日志 |
| 制造504或上游断流 | error可见，不伪装done；可按策略重试 | 错误码/事件与时间线 |
| 提交一次审批并重复提交 | 仅一次副作用，第二次有明确状态 | 动作账本、数据库行、供应商调用数 |
| 未登录/跨租户/坏输入 | 401/404/422，响应不泄露 | 集成测试与真实请求 |
| 429/504 | 用户可理解，日志有分类 | 状态码、错误体、requestId |
| 干净库与已有库各跑迁移 | 都到同一schema版本 | 迁移命令、版本、退出码 |
| 重启后查资料/会话/审批 | 仍存在；过期会话仍拒绝 | 重开存储后的查询/请求 |
| 切回上一digest | 代码恢复且数据库兼容，主路径复验 | digest、迁移版本、回滚记录 |

最后确认回滚命令引用固定镜像 digest，且数据库处于兼容状态。配套测试通过只证明已覆盖的切片，不替代真实模型、浏览器 E2E、Docker运行或正式安全验收；表中未执行项保持“待验证”。

## 7. 面试问答与参考回答

**问：为什么部署要用不可变镜像？**

保证测试/预发/生产运行同一份产物，只换配置；避免服务器现场构建导致“我机器上能跑”。回滚也只需切回上一个 digest。

**问：数据库迁移怎样支持回滚？**

用扩展/收缩：先加兼容结构、双写/回填、切读、旧实例退出后再删。代码可回滚，数据迁移通常不可逆；破坏性变更要分多次发布。

**问：健康检查和就绪检查有什么区别？**

health/liveness 表示进程活着，失败可重启；ready 表示能接流量（依赖/迁移就绪），失败只摘流量，不重启。liveness 不应依赖外部上游。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 怎样把“本机能跑”变成可复现构建、兼容迁移、可回滚发布和能被逐项验收的 Capstone？

**一条主线：**

```text
锁文件构建 + 启动时配置校验
→ 迁移/健康检查/发布
→ 固定 digest + 验收矩阵与回滚方案
```

**三个关键词：** 不可变产物、兼容迁移、验收矩阵。同一digest跨环境，扩展/收缩保护回滚，逐项证据区分已实现与待验证。

**最容易错：**
- 把当前dist/host直接套进dist/client/server模板；忽略127.0.0.1容器监听。
- 用latest/服务器现场构建；缺配置到请求期才500，密钥进镜像或日志。
- 发布同刻删列，或只回滚代码不检查数据库兼容；把health当ready。
- 用`pnpm start`代替serve；Capstone只展示成功路径或把模板目标勾成完成。

**与前后章：** 第17章提供requestId、TTFT、成本和风险检查；附录A把发布与回滚决策讲成可追问的工程答案。

**学完应能：** 说明当前产物/模板差异，记录构建→迁移→健康→发布→回滚；用三项练习和验收矩阵交付可复现证据。

### 8.2 参考与后续学习

参考：[Docker multi-stage](https://docs.docker.com/build/building/multi-stage/)、[The Twelve-Factor App](https://12factor.net/)、[Kubernetes probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)。

[上一章](17-可观测性与成本安全.md) · [全书目录](教材目录.md) · [附录A](附录A-面试题与参考回答.md)
