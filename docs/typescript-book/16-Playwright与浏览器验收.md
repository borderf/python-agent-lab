# 第16章　Playwright 与浏览器验收

[上一章](15-Vitest与契约测试.md) · [全书目录](教材目录.md) · [下一章](17-可观测性与成本安全.md)

## 1. 学习目标与前置知识

能用 Playwright 覆盖一条真实用户主路径，按角色/标签定位元素，处理登录状态、网络替身和异步等待；能做基本可访问性检查，并让 E2E 在 CI 稳定运行。前置：第 8–10、15 章。

**本章从这里开始：** 单元测试全绿，但用户点“搜索”没反应；按钮在加载时重复提交；键盘无法打开引用；移动端布局把“停止”遮住。浏览器验收不是“截图好看”，而是证明**用户能完成任务**。

**实施范围：** 配套工程已有 React 搜索宿主、Node BFF、来源摘要面板和 jsdom Hook 回归；`pnpm build` 后可用 `pnpm serve` 启动。尚无登录页、独立原文来源页或 Playwright 依赖。先按[最小切片](../project-practice/最小全栈切片.md)启动，再安装并锁定测试依赖、配置 baseURL/webServer。以下“完整来源”和登录片段属于后续扩展，不能直接用当前 pnpm test 声称 E2E 已通过。最小主路径先用固定教学身份，Cookie 登录留到第13章扩展完成后。

## 2. 基础知识讲解

### 2.1 E2E 只覆盖关键路径

推荐只测：

- 登录/未登录跳转；
- 搜索 → 结果 → 打开引用；
- 提问 → 流式文本 → 完成/停止；
- 审批 → 状态更新（如果本期有）；
- 一个关键错误/空状态。

不要把每个字段校验都放 E2E；那些用单元/集成测试更快。E2E 数量少、价值高、维护贵。

### 2.2 用角色/标签定位

```ts
import { test, expect } from "@playwright/test";

test("搜索并打开引用", async ({ page }) => {
  await page.goto("/");
  const search = page.getByRole("region", { name: "文档搜索" });
  await search.getByLabel("问题").fill("预付款");
  await search.getByLabel("业务日期").fill("2026-07-01");
  await search.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByRole("list", { name: "搜索结果" })).toBeVisible();
  await page.getByRole("button", { name: "打开来源 policy-a" }).click();
  await expect(page.getByRole("heading", { name: /付款制度/ })).toBeVisible();
});
```

`getByRole`/`getByLabel` 与可访问性树一致，比 CSS 选择器稳定，也迫使界面有正确语义。避免 `page.locator("div > button:nth-child(2)")`，样式一改就碎。

最后的标题来自你实现的来源展示宿主，不是SearchPage自动提供的路由；它的onOpenSource只通知调用方。来源请求必须重新授权，不能由猜测URL代替。短暂loading可能在断言前已经结束；若专门测试加载态，要让测试服务受控地延迟响应，不把每次主路径都绑定在中间态上。

### 2.3 登录状态复用

```ts
// playwright/auth.setup.ts
import { test as setup } from "@playwright/test";

setup("登录一次", async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error("先配置隔离测试账号的E2E_PASSWORD");
  await page.goto("/login");
  await page.getByLabel("邮箱").fill("demo@example.com");
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await page.context().storageState({ path: "playwright/.auth/user.json" });
});
```

测试项目配置 `storageState`，避免每个用例重复登录。Cookie 会话的 `storageState` 包含 Cookie；不要把它提交到仓库，`.gitignore` 掉。

该段仅用于已实现登录页的升级工程；当前教学Bearer工厂没有/login页面。不能为了让测试运行而用空密码或伪造登录成功。等待登录成功标志、确认会话有效后再保存storageState。

### 2.4 网络替身

```ts
test("空结果有明确提示", async ({ page }) => {
  await page.route("**/api/search", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ items: [] }),
  }));
  await page.goto("/");
  const search = page.getByRole("region", { name: "文档搜索" });
  await search.getByLabel("问题").fill("不存在的条款");
  await search.getByLabel("业务日期").fill("2026-07-01");
  await search.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByText("没有找到相关条款")).toBeVisible();
});
```

E2E 用网络替身测 UI 状态，不依赖真实模型/数据库；真实集成另有一条“冒烟”路径，环境变量控制，不在每次 PR 跑。

流式 UI 的 E2E 有两种：用假 SSE 服务返回完整事件序列，断言最终文本/引用；或用真实测试服务做一次冒烟。Playwright `route.fulfill` 是一次性 body，不适合验证“逐字到达”的时序；时序用单元测试/组件测试。

### 2.5 等待状态，不要等待时间

```ts
const searchStatus = page.getByRole("status", { name: "搜索状态" });
await expect(searchStatus).toHaveText("搜索中…");
await expect(searchStatus).toBeHidden();
await expect(page.getByText("预付款比例不得超过20%")).toBeVisible();
```

`waitForTimeout(3000)` 是 flaky 的根源；用 `expect` 的自动重试等待可观察状态。需要等待网络时用 `page.waitForResponse`，但要匹配具体 URL/方法。

### 2.6 可访问性

- 所有输入有 `<label>`；按钮文本说明动作；
- 键盘 Tab 顺序合理，焦点可见；
- 错误用 `role="alert"`，加载用 `role="status"`；
- 流式区域不要每 token 都打断读屏；完成时播报摘要；
- 颜色对比、放大 200% 不丢失内容。

```ts
import AxeBuilder from "@axe-core/playwright";

test("首页无严重可访问性问题", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});
```

axe 只能发现一部分问题，不能替代键盘/读屏手工检查。

### 2.7 CI 与稳定性

```powershell
pnpm exec playwright install --with-deps chromium
pnpm exec playwright test
```

- 固定浏览器版本；失败保留 trace/video/screenshot；
- 每个测试独立上下文，不共享登录/数据库状态；
- 测试数据用工厂/固定 ID，避免“第 1 条”这种位置依赖；
- 对不稳定用例先修根因，不要加大超时掩盖。

### 2.8 最小配置的输入输出边界

Playwright尚未安装；接入时先锁定依赖，再建立配置。最小配置应明确：

| 配置项 | 本章建议 | 原因 |
| --- | --- | --- |
| testDir | `e2e` | 与当前Node `tests/*.test.mjs`分开 |
| baseURL | `http://127.0.0.1:8787` | 与`pnpm serve`默认端口一致 |
| webServer命令 | 先`pnpm build`再`pnpm serve` | 当前服务读dist与host/app.js |
| reuseExistingServer | 本地可复用，CI关闭 | 避免误连旧服务 |
| trace/video/screenshot | 失败保留 | 提供可诊断证据 |
| projects | 先Chromium桌面，再补移动视口 | 先跑通主路径，不一次铺满 |

端口可用环境变量替换，但配置与实际服务必须一致。当前`pnpm start`运行离线`dist/main.js`，不是Web服务器；把它填进webServer会出现连接拒绝。

### 2.9 网络替身、真实冒烟与时序测试的分工

| 方式 | 能证明 | 不能证明 |
| --- | --- | --- |
| `route.fulfill`固定JSON | 空态、错误提示、字段渲染、按钮交互 | BFF/Python/数据库协作 |
| 本地真实BFF+Python | HTTP契约、身份、持久化切片 | 公网模型、所有浏览器布局 |
| 假SSE完整body | token/citation/done的最终状态 | token是否逐步到达、50ms批量 |
| 真实/受控流服务 | 流传输、停止、断连 | 供应商计费是否停止 |
| 单元/组件测试 | 精确的迟到、buffer、reducer顺序 | 键盘、焦点、视口遮挡 |

`route.fulfill`适合一次响应；若要验证“第一个token先出现、done后状态变化”，需要能分块发送的测试服务，而不是把完整SSE字符串一次返回。此类服务目前未提供，不能把完整body测试写成流式时序已通过。

### 2.10 常见失败与定位顺序

| 现象 | 优先检查 | 不应怎么做 |
| --- | --- | --- |
| 页面连接拒绝 | build是否成功、serve是否启动、端口/baseURL | 只加大test超时 |
| 搜索按钮无反应 | 是否重复点击被禁用、请求是否发出、alert文本 | 直接改选择器绕过语义 |
| 结果列表等不到 | 路由URL/method、BFF响应字段、网络状态 | 用`waitForTimeout`赌完成 |
| 来源点击后无标题 | 当前是页内SourcePanel，不是独立路由 | 断言不存在的`/sources/:id` |
| 流式停止后文字消失 | stop是否flush、runner是否迟到、aria状态 | 只检查abort次数 |
| CI偶发失败 | trace、共享Cookie/数据库、未等待Promise | 重跑直到绿或统一加30秒 |

## 3. 原理讲解与推导

### 3.1 E2E 证明“集成后仍可用”

单元测试证明函数正确，E2E 证明路由、渲染、事件、网络和浏览器协作后用户仍能完成任务。它不证明内部算法正确，也不适合覆盖所有分支。

### 3.2 选择器即契约

用角色/标签定位，等于把“界面语义”当契约。改按钮文字会 break 测试，这是提醒你同步更新可访问名称；用 CSS 类则样式重构就 break，信号价值低。

### 3.3 测试环境要可控

E2E 依赖服务、数据库、模型。用固定 fixture/替身控制输入；真实模型只做单独冒烟，不进入每次 PR，否则测试慢且不确定。

### 3.4 等待的本质是建立“条件已满足”的证据

`expect(locator).toBeVisible()`会重试读取同一个可观察条件，直到成立或超时；它比“睡3秒”更早继续，也更晚才失败。`page.waitForResponse`匹配具体URL/方法，若在click之后才注册，快速响应可能已经发生。需要响应内容时，应先创建等待Promise，再执行点击，最后await并检查状态/body。

自动重试只解决“何时观察到”，不修复重复提交、错误路由或闪屏。若loading态只存在20ms，主路径不应强制等待它；专门测loading时，用受控延迟保持该状态，并同时验证按钮禁用和最终结果。

## 4. 示例与逐步走查

```ts
// e2e/search.spec.ts；需要已接好的宿主页与网络适配器
import { test, expect } from "@playwright/test";

test.describe("搜索主路径", () => {
  // 最小教学宿主页提供固定测试身份；实现真实登录后再启用storageState。

  test("输入问题、看到结果、打开来源", async ({ page }) => {
    await page.route("**/api/search", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [{
        sourceId: "policy-a", version: "2", title: "付款制度", quote: "预付款比例不得超过20%。",
        location: { kind: "source", section: "第1条" },
      }] }),
    }));

    await page.goto("/");
    const search = page.getByRole("region", { name: "文档搜索" });
    await search.getByLabel("问题").fill("预付款");
    await search.getByLabel("业务日期").fill("2026-07-01");
    await search.getByRole("button", { name: "搜索" }).click();

    const results = page.getByRole("list", { name: "搜索结果" });
    await expect(results).toBeVisible();
    await expect(results.getByText("预付款比例不得超过20%。")).toBeVisible();
    await results.getByRole("button", { name: "打开来源 policy-a" }).click();
    await expect(page.getByRole("heading", { name: "付款制度" })).toBeVisible();
  });
});
```

逐步解释：

1. 宿主先给SearchPage注入测试身份、load与onOpenSource；load消费BFF的SearchHit契约；
2. 这里mock的是已映射的BFF响应；直连Python时必须使用附录B的snake_case原始夹具并经过适配，不能混用；
3. 定位用角色/名称，界面语义变化会明确失败；
4. 断言用户可见结果，不断言内部 state；
5. 真实服务冒烟另设项目/环境变量，不在每次 PR 跑。

### 4.1 当前宿主页哪些断言有真实落点

| 页面元素 | 当前实现 | 可写断言 | 不能推断 |
| --- | --- | --- | --- |
| 搜索表单 | SearchPage，业务日期输入 | 点击后出现命名“搜索结果”列表 | 已通过真实键盘/移动端验收 |
| 来源摘要 | SourcePanel显示title/version/quote/location | 点击“打开来源 policy-a”后标题“付款制度”可见 | 已有独立原文路由或再次授权 |
| 流式回答 | AnswerPanel按钮名“开始回答” | token文本、停止后保留、error alert | 第10章AnswerPage双字段已兼容 |
| 健康检查 | `GET /health`返回`{status:"ok"}` | 服务可启动 | 已有`/ready`或生产依赖就绪 |
| 登录 | 固定教学Bearer demo | 未认证API返回401 | 已有/login或Cookie会话 |

当前AnswerPanel只发送question；若测试第10章AnswerPage，需要先调整它的body或扩展端点。`article aria-live="polite"`会随流更新，是否过度播报必须用真实读屏/浏览器检查，不能由jsdom测试推断。

## 5. 练习

### 5.1 跟写

写“空结果”和“搜索失败”两条 E2E：前者断言空状态，后者断言 `role="alert"` 和重试按钮。

### 5.2 改造

给流式回答写 E2E：用假 SSE 服务返回 token/citation/done，断言最终文本、引用和“待复核”；再用停止按钮断言保留部分文本。

### 5.3 独立

用 axe 检查搜索页/回答页，修复至少一个 serious 问题（label、对比度、焦点）；记录修复前后截图和键盘操作路径。

## 6. 验收与自测

**行为验收目标：** 完成宿主页与Playwright配置后，主路径在CI稳定通过，失败有trace，键盘可完成搜索/停止，错误/空状态可见，移动端关键按钮不被遮挡。当前jsdom检查不算这些目标已经完成。

**原理验收：** 能解释 E2E 的边界、角色选择器的价值、网络替身与真实冒烟的分工；能说出一个 flaky 测试的根因。

| 操作 | 预期 | 证据 |
| --- | --- | --- |
| 填问题/日期，点击“搜索” | 命名结果列表与引文可见 | E2E截图/断言/trace |
| 点击“打开来源 policy-a” | 页内来源摘要标题可见 | 同一测试的后续断言 |
| 路由返回空items | 明确空态，不是加载永久转圈 | 空结果E2E |
| 路由返回502错误体 | `role="alert"`与重试入口可见 | 失败E2E |
| 点击“开始回答”后停止 | 已到文本保留，停止状态可见 | 受控SSE服务E2E |
| 仅用Tab/Enter完成搜索与停止 | 焦点可见，关键按钮可达 | 键盘路径记录 |
| 移动视口打开回答面板 | 停止按钮不被遮挡 | 视口截图/边界检查 |
| axe扫描 | 无新增serious/critical；人工问题另记 | axe JSON与手工检查 |

当前没有Playwright依赖、配置或运行记录，以上全部是实施后的验收目标。现有`react.test.mjs`只能作为Hook回归证据。

### 6.1 先预测，再查看解释

用 `waitForTimeout(3000)` 等搜索结果，为什么在 CI 更容易失败？

<details>
<summary>完成预测后查看解释</summary>

固定等待假设“3 秒内一定完成”；CI 负载、冷启动、网络波动都可能超过。应等待可观察状态（元素出现/文本变化/响应完成），让测试在条件满足时立即继续，而不是赌时间。

</details>

## 7. 面试问答与参考回答

**问：E2E 应该覆盖多少？**

少而关键：登录、主任务、核心错误/空状态、一次关键写入。字段级分支用单元/集成测试；E2E 维护成本高，覆盖过多会慢且 flaky。

**问：为什么用角色选择器而不是 CSS？**

角色/名称对应可访问性树，和用户/读屏看到的结构一致；CSS 类与样式耦合，重构就失败，信号价值低。

**问：怎样减少 E2E flaky？**

独立上下文/数据、等待可观察状态、固定网络替身、固定浏览器版本、失败保留 trace；不要靠加大超时掩盖竞态。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 怎样用真实浏览器证明“用户能完成任务”，同时让 E2E 稳定、可诊断、不冒充全量验证？

**一条主线：**

```text
用户主路径
→ 角色/标签定位 + 状态等待 + 网络替身/登录复用
→ 稳定通过 + trace + 可访问性证据
```

**三个关键词：** 主路径、语义定位、可观察状态。只测关键任务，用角色/标签对齐用户语义，等待真实状态并保留trace。

**最容易错：**
- 固定sleep或脆弱CSS定位；把一次性SSE body当逐token时序。
- 误用`pnpm start`当Web服务；把页内SourcePanel当独立来源路由。
- 提交storageState、共享登录/数据库状态，或重跑直到绿掩盖竞态。
- 只测成功路径；把jsdom/axe通过当键盘、读屏、移动端全部通过。

**与前后章：** 第15章提供后端与契约证据；第17章把浏览器请求、TTFT、错误与成本关联到requestId。

**学完应能：** 为搜索→来源→停止写最小E2E；说明替身/冒烟/时序分层；用trace和键盘路径诊断失败。

### 8.2 参考与后续学习

参考：[Playwright](https://playwright.dev/docs/intro)、[Testing Library queries](https://testing-library.com/docs/queries/about/)、[axe-core](https://github.com/dequelabs/axe-core-npm)。

[上一章](15-Vitest与契约测试.md) · [全书目录](教材目录.md) · [下一章](17-可观测性与成本安全.md)
