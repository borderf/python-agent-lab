# 第15章　测试分层、契约与Vitest迁移

[上一章](14-AI-SDK与工具调用.md) · [全书目录](教材目录.md) · [下一章](16-Playwright与浏览器验收.md)

## 1. 学习目标与前置知识

能从一个具体失败选择测试层，保留真实规则、替换外部边界，并解释每条通过到底证明了什么。前置：第6、8–12章的累计实现。

**本章从这里开始：** 页面看起来正常，但旧请求的取消回调清掉了新请求的缓冲；单元测试全绿，SQL却把日期值当列；前后端各自类型正确，接口字段仍对不上。先复现其中一个失败，再选测试工具。

配套工程当前用Node内置test runner执行回归，`pnpm test`会先编译。它已经调用真实React、Hono和SQLite。Vitest是本章最后的迁移练习，目前不在锁文件中；Playwright也尚未执行。不要把工具学习示意当成现有测试结果。

## 2. 基础知识讲解

### 2.1 先选择被测行为，再选择测试层

| 问题 | 被测规则与真实依赖 | 可以替换什么 | 当前入口 |
| --- | --- | --- | --- |
| 一个SSE事件跨字节切开会怎样 | 解码、分帧、业务校验都保留 | 网络字节来源 | core.test.mjs |
| 旧请求取消会不会破坏新状态 | 控制器、Hook、React生命周期都保留 | 可控制先后完成的runner | core/react.test.mjs |
| 搜索路由是否接受伪造租户 | Hono、中间件、参数与错误映射都保留 | authenticate和上游HTTP边界 | integration.test.mjs |
| 日期右端与批量回滚 | 真实Drizzle和SQLite引擎 | 测试数据 | integration.test.mjs |
| Python响应字段变化 | Python真实HTTP响应、冻结夹具、TS适配器 | fixture模型 | Python与TS两端检查 |
| 键盘和手机能否完成任务 | 真实页面、浏览器与事件链 | 固定模型/测试账号 | 第16章待完成 |

这些层相互补充：真实React在jsdom中执行，仍不能证明真实浏览器布局；SQLite通过不能证明PostgreSQL锁语义；上游替身不能证明公网网络和模型兼容。

### 2.2 从失败输入写一个最小断言

先在配套工程执行：

```powershell
pnpm typecheck
pnpm test
```

再读[核心测试](../../typescript-examples/tests/core.test.mjs)。每项都先构造导致错误的输入，再调用真实函数，最后检查可观察输出。例如无引用却needsReview=false，应该在解析阶段失败，不能等页面自行猜测是否可信。

以下是可单独保存为`tests/review-answer.test.mjs`的小练习，位于同一个工程并使用构建产物：

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseAnswer } from "../dist/contracts.js";

test("无引用的回答必须保留复核提示", () => {
  const result = parseAnswer({ answer: "缺乏依据", citations: [], needsReview: false });
  assert.equal(result.ok, false);
});
```

故意删除解析器的这条规则，确认测试转红，再恢复。若测试仍绿，就检查它是否真的调用了刚修改的产物：先build、再运行，不要测旧dist。

### 2.3 异步测试必须控制完成顺序

旧请求问题的关键不是“等待100毫秒”，而是制造确定顺序：A开始 → B开始 → B收到token → A迟到拒绝 → B完成。假runner即使不响应取消，也不能让A重新获得发布状态的权限。

[React测试](../../typescript-examples/tests/react.test.mjs)用真实Hook、StrictMode和`act`走这个顺序。断言B的文字保留、停止前的尾部缓冲被刷新、换身份后旧数据不可见。只检查abort被调用一次，无法证明这些行为。

定时器也需要清理：卸载后不再发布，旧finally不能清新timer。伪时钟适合测明确的调度；网络与数据库集成使用真实等待机制。Promise的拒绝断言必须在触发拒绝前或同一受控异步操作内接好，避免未处理拒绝。

### 2.4 路由集成保留Hono，替换上游

读[集成测试](../../typescript-examples/tests/integration.test.mjs)。`createBff`接收authenticate、fetcher和timeoutMs，测试不用启动端口就能调用`app.request`。合法请求与拒绝请求都要有：否则一个永远返回401的程序也能通过“无令牌返回401”。

超时由deadline信号触发；上游单独抛名为AbortError的错误，不足以证明超时。客户端取消、BFF预算用尽、上游422、网络失败分别检查。不要stub全局fetch后忘记恢复，也不要把鉴权、正文校验和错误映射本身mock掉。

当前只有search/health路由。第13章来源授权路由还需自己实现，不能用“不存在的路径返回404”证明跨租户隔离：必须配一条同租户成功读取，以及另一租户无法读取的测试。

### 2.5 数据库测试检查真正提交的事实

集成测试使用SQLite WASM引擎和真实Drizzle：插入 → 按租户与日期读取 → 相同版本重试 → 冲突 → 导出并重新打开。批量后半段冲突时，检查前半段也没有留下；仅assert抛错不代表事务回滚。

每个测试独立数据库并在finally关闭。它验证当前SQLite适配，不验证原生驱动文件同步、进程崩溃、迁移或多实例竞争；这些要增加对应环境和故障注入。

### 2.6 跨语言契约怎样连接

Python测试[响应契约](../../tests/test_typescript_contract.py)实际调用两份HTTP服务，对照两份[固定响应夹具](../../typescript-examples/tests/fixtures/search-core.json)与[持久服务夹具](../../typescript-examples/tests/fixtures/search-persistent.json)。TS再让这些相同夹具通过`parseSearchResponse`。字段漂移会在任一侧失败。

这比只在TS中手写一个理想对象更接近真实协作，但仍是有限样本。增加日期、权限错误、空列表、长文本时，把相应响应也纳入检查；若使用OpenAPI生成类型，仍保留运行时校验。生成的静态类型不保证网络响应可信。

### 2.7 Vitest作为迁移练习

测试行为与runner不是同一件事。在独立练习分支选择并锁定兼容Node22的Vitest版本，再将上面的小练习迁移到`vitest/answer.test.ts`：

```ts
import { expect, it } from "vitest";
import { parseAnswer } from "../src/contracts.js";

it("无引用的回答必须保留复核提示", () => {
  expect(parseAnswer({ answer: "缺乏依据", citations: [], needsReview: false }).ok).toBe(false);
});
```

接着迁移一项异步和一项Hono测试，核对相同反例都会失败。新增测试目录、类型检查配置与CI脚本要一起更新，不能把Vitest文件混进当前Node runner的`tests/*.test.mjs`收集范围。使用expectTypeOf时，还需启用类型检查；普通运行成功不等于类型断言已执行。本章不要求为换工具重复重写所有已覆盖行为。

## 3. 原理讲解与推导

### 3.1 为什么全绿仍可能错误

测试只约束输入集合上的行为。把校验器mock成true，检查永远成功；只测未登录，拒绝一切也成功；只测整段SSE，跨字节解码仍可能坏。增加数量不自动补这些缺口。先问“什么错误实现也能过”，再加能区分它的反例。

### 3.2 编译、运行和真实环境是三种证据

tsc检查类型与导入，不能证明SQL与事件先后；集成测试检查实际框架协作，不能证明浏览器布局和生产负载。每份验收记录写清：输入、环境、替身、实际依赖、输出与未覆盖范围。覆盖率只是遗漏线索，不代表用户任务完成。

### 3.3 确定性不等于删掉失败

用可控runner、固定文档和独立数据库消除偶然时序，仍要保留失败输入。不能为让CI稳定就删除取消、超时和坏数据。出现偶发失败时先找共享状态与未等待Promise，不先增加等待时长。

## 4. 示例与逐步走查

沿同一个“按日期搜索”功能走四步：

1. `pnpm typecheck`：先确认页面、Hook、BFF和数据库模块能一起编译。
2. `pnpm test`：在集成输出中定位“合法搜索”“伪造租户”“总时限”“半开日期”，说明各自保留的真实依赖。
3. 查看两份Python夹具的不同粒度：core含chunk_id/start/end，persistent含section；适配器不能凭空补片段偏移。删一个必填字段，必须失败。
4. 改一个未测条件：例如上游错误JSON、身份撤销、重复引用，再选择一层增加测试。浏览器主路径留到下一章，不用路由断言替代点击路径。

当前[CI](../../.github/workflows/typescript.yml)在Node22中锁文件安装、typecheck、test并运行累计脚本；Python工作流另验真实响应。它没有发布应用，也没有启动真实浏览器或供应商模型。

## 5. 练习

### 5.1 跟写

完成上面的无引用反例，并让一次故意破坏转红。说明失败发生在编译、解析还是状态转换。

### 5.2 改造

扩展SSE与Hook现有测试：未知事件、坏JSON、提前断流、停止后迟到token、A取消晚于B开始。保留中文和emoji的按字节切片；不要只按JavaScript字符切片模拟网络。

### 5.3 独立

实现来源授权路由后，为同租户成功与跨租户失败各写一条集成检查；再完成Vitest迁移练习。每项写出一个仍未证明的边界，不追求所有内部函数各配一条重复测试。

## 6. 验收与自测

**行为验收：** 现有基线通过，能新增一个真实反例并观察转红；类型、路由、数据库、跨语言响应的证据能分别定位。扩展功能按自己的实现验收，不把未来目标记成通过。

**原理验收：** 能说明真实依赖、替身、失败输入和证明边界；能解释全绿为何不等于完整产品可用。

### 6.1 先预测，再查看解释

任意未知来源ID都返回404，这能证明跨租户保护正确吗？

<details><summary>完成预测后查看解释</summary>

不能。路由可能根本不存在，也可能拒绝所有请求。先由租户A创建并成功读取一个来源，再由租户B用相同ID读取，检查统一404且响应不泄露标题/正文；同时保留真实身份与授权逻辑。

</details>

## 7. 面试问答与参考回答

**问：你如何证明取消竞争问题已修复？** 受控地让A开始、B开始、B收token后A才拒绝，真实Hook中B内容仍完整；卸载和身份切换也检查。仅断言AbortController调用次数不能证明没有旧回调发布。

**问：契约测试与类型检查有什么区别？** 类型检查约束当前源码；契约检查实际响应字段与错误。这里Python真实响应固定为夹具，TS对同一夹具做运行时解析，两端CI发现漂移，但有限样本还需扩展。

**问：为什么不用所有真实依赖？** 外部模型与公网不可控，频繁回归用可控边界；框架、校验、数据库规则仍保留真实实现。真实模型和部署另做记录完整的冒烟，不能用替身结果宣称已验证。

## 8. 本章小结与参考

先用失败输入定义行为，再选择层和runner。编译、实际依赖回归、跨语言契约、真实浏览器与部署分别补足证据；工具名不代表完成程度。

参考：[Node测试工具](https://nodejs.org/api/test.html)、[Vitest](https://vitest.dev/guide/)、[Hono Testing](https://hono.dev/docs/guides/testing)。

[上一章](14-AI-SDK与工具调用.md) · [全书目录](教材目录.md) · [下一章](16-Playwright与浏览器验收.md)
