# 第16章　Playwright 与浏览器验收

[上一章](15-Vitest与契约测试.md) · [全书目录](教材目录.md) · [下一章](17-可观测性与成本安全.md)

## 1. 学习目标与前置知识

能用 Playwright 覆盖一条真实用户主路径，按角色/标签定位元素，处理登录状态、网络替身和异步等待；能做基本可访问性检查，并让 E2E 在 CI 稳定运行。前置：第 8–10、15 章。

**本章从这里开始：** 单元测试全绿，但用户点“搜索”没反应；按钮在加载时重复提交；键盘无法打开引用；移动端布局把“停止”遮住。浏览器验收不是“截图好看”，而是证明**用户能完成任务**。

**实施范围：** 配套工程目前有可编译组件与jsdom中的真实Hook回归，尚无可启动的浏览器宿主页、登录页或Playwright依赖。本章是下一段实施练习，以下片段需先接好宿主页、网络适配、来源打开回调，再安装并锁定测试依赖、配置baseURL/webServer；不能直接运行当前pnpm test就声称E2E通过。最小主路径先用固定教学身份，Cookie登录留到第13章扩展完成后。

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
  await page.getByLabel("问题").fill("预付款");
  await page.getByLabel("业务日期").fill("2026-07-01");
  await page.getByRole("button", { name: "搜索" }).click();
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
  await page.getByLabel("问题").fill("不存在的条款");
  await page.getByLabel("业务日期").fill("2026-07-01");
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByText("没有找到相关条款")).toBeVisible();
});
```

E2E 用网络替身测 UI 状态，不依赖真实模型/数据库；真实集成另有一条“冒烟”路径，环境变量控制，不在每次 PR 跑。

流式 UI 的 E2E 有两种：用假 SSE 服务返回完整事件序列，断言最终文本/引用；或用真实测试服务做一次冒烟。Playwright `route.fulfill` 是一次性 body，不适合验证“逐字到达”的时序；时序用单元测试/组件测试。

### 2.5 等待状态，不要等待时间

```ts
await expect(page.getByRole("status")).toHaveText("搜索中…");
await expect(page.getByRole("status")).toBeHidden();
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

## 3. 原理讲解与推导

### 3.1 E2E 证明“集成后仍可用”

单元测试证明函数正确，E2E 证明路由、渲染、事件、网络和浏览器协作后用户仍能完成任务。它不证明内部算法正确，也不适合覆盖所有分支。

### 3.2 选择器即契约

用角色/标签定位，等于把“界面语义”当契约。改按钮文字会 break 测试，这是提醒你同步更新可访问名称；用 CSS 类则样式重构就 break，信号价值低。

### 3.3 测试环境要可控

E2E 依赖服务、数据库、模型。用固定 fixture/替身控制输入；真实模型只做单独冒烟，不进入每次 PR，否则测试慢且不确定。

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
    await page.getByLabel("问题").fill("预付款");
    await page.getByLabel("业务日期").fill("2026-07-01");
    await page.getByRole("button", { name: "搜索" }).click();

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

- E2E 覆盖关键用户路径，不替代单元/集成测试。
- 角色/标签定位，等待状态，不等待固定时间。
- 登录复用，网络替身，真实服务只做冒烟。
- 可访问性是验收项：键盘、标签、错误/状态语义。

参考：[Playwright](https://playwright.dev/docs/intro)、[Testing Library queries](https://testing-library.com/docs/queries/about/)、[axe-core](https://github.com/dequelabs/axe-core-npm)。

[上一章](15-Vitest与契约测试.md) · [全书目录](教材目录.md) · [下一章](17-可观测性与成本安全.md)
