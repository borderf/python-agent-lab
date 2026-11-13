# 第18章　部署、回滚与 Capstone

[上一章](17-可观测性与成本安全.md) · [全书目录](教材目录.md)

## 1. 学习目标与前置知识

能把 TypeScript 全栈应用打成可复现的构建产物，用容器/环境变量/迁移/健康检查部署，设计回滚与兼容迁移；能按验收矩阵交付 DocPilot Console，而不是“本机能跑”。前置：第 7、11–17 章。

**本章从这里开始：** 本地 `pnpm dev` 正常，CI 构建失败；数据库迁移先删列，旧实例还在写；发布后健康检查通过，但用户搜索全 500。部署不是“传上去”，是**构建、迁移、启动、验证、回滚**一整套可重复流程。

**当前起点：** 配套工程是类型检查与回归实验，尚无Vite宿主页、Node监听入口、迁移脚本或Dockerfile。本章给出交付设计与模板，需要你补齐入口并实际构建验证；它不是当前工程直接可执行的部署recipe。先完成第16章宿主与浏览器主路径，再扩真实会话、流式后端与写审批；不要用pnpm start的离线脚本代替服务启动。

## 2. 基础知识讲解

### 2.1 构建产物与运行环境

当前配套工程可执行下列命令，但它的build只编译实验模块，不产生完整前后端应用：

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
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

### 2.2 先补一条最小宿主，而不是同时补所有组件

最小可访问路径只需要四步：浏览器搜索 → BFF 转发 → Python DocPilot 返回结果 → 打开来源。先建下面三个文件，不要一开始加流式、会话和审批：

```text
apps/web/index.html
apps/web/src/main.ts       表单、fetch /api/search、渲染列表与来源链接
apps/server/server.ts      Hono BFF：/api/search 转发到 DOCPILOT_URL
```

`main.ts` 的核心约束：

- 用 `textContent` 渲染用户/模型文本，不把返回内容拼进 `innerHTML`；
- 每个结果链接到 `/sources/:sourceId`，保留 source/version 参数；
- 请求失败显示错误与重试，不显示空列表冒充“没有结果”。

宿主验收命令：

```powershell
pnpm dev
pnpm exec playwright test tests/search.spec.ts
```

Playwright 先 `page.route("**/api/search", ...)` 固定一条结果，再断言搜索框、结果列表和来源链接可操作；随后用真实 BFF + Python 服务跑一次冒烟。完成这条路径后，再按第10、14章逐步加流式回答、工具轨迹和审批，不要反过来同时补所有组件。

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

export const config = {
  port: Number(process.env.PORT ?? 8787),
  databaseUrl: required("DATABASE_URL"),
  docpilotUrl: required("DOCPILOT_URL"),
  sessionSecret: required("SESSION_SECRET"),
};
```

启动时失败优于运行时 `undefined`。端口还应检查为1–65535范围的整数，不能只用Number接受NaN或小数。密钥用平台secret/环境变量注入，不进镜像、不进仓库、不进日志。不同环境用不同配置，但构建产物尽量一致。

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

## 5. Capstone：DocPilot Console

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

## 6. 练习

### 6.1 跟写

写多阶段 Dockerfile 和 `.dockerignore`，构建镜像并以非 root 运行；用 `/health`/`/ready` 做容器健康检查。

### 6.2 改造

设计一次兼容迁移：给 `documents` 加 `checksum` 列，双写/回填/切换读/旧实例退出后再删旧逻辑；写回滚步骤。

### 6.3 独立

按验收矩阵做一次完整演示，录屏/截图/命令记录；请另一人按 README 从干净环境启动，记录卡点。

## 7. 面试问答与参考回答

**问：为什么部署要用不可变镜像？**

保证测试/预发/生产运行同一份产物，只换配置；避免服务器现场构建导致“我机器上能跑”。回滚也只需切回上一个 digest。

**问：数据库迁移怎样支持回滚？**

用扩展/收缩：先加兼容结构、双写/回填、切读、旧实例退出后再删。代码可回滚，数据迁移通常不可逆；破坏性变更要分多次发布。

**问：健康检查和就绪检查有什么区别？**

health/liveness 表示进程活着，失败可重启；ready 表示能接流量（依赖/迁移就绪），失败只摘流量，不重启。liveness 不应依赖外部上游。

## 8. 本章小结与参考

- 构建/类型/测试/镜像在 CI 完成，产物不可变。
- 配置启动时校验，密钥不进镜像/日志/前端。
- 迁移用扩展/收缩，发布用 digest，异常先回滚。
- Capstone 用验收矩阵和失败案例证明，不用“能跑”代替。

参考：[Docker multi-stage](https://docs.docker.com/build/building/multi-stage/)、[The Twelve-Factor App](https://12factor.net/)、[Kubernetes probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)。

[上一章](17-可观测性与成本安全.md) · [全书目录](教材目录.md) · [附录A](附录A-面试题与参考回答.md)
