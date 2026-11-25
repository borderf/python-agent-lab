# 第08章　React 组件、状态与数据流

[上一章](07-模块构建与工程化.md) · [全书目录](教材目录.md) · [下一章](09-异步数据缓存与错误边界.md)

## 1. 学习目标与前置知识

能把界面拆成组件，用 props 传数据、用 state 表达变化，用判别联合表示加载/流式/完成/失败，用 `useEffect` 同步外部资源并在卸载时清理，并用 `useRef/useMemo/useCallback/useId` 稳定引用与关联表单。前置：第 1–7 章；会 JavaScript/TS 函数与对象；DOM/React 基础不熟先读[附录D](附录D-JavaScript与浏览器基础.md)。

**本章从这里开始：** 搜索框、结果列表和错误提示放在一起时，先问：搜索词存在哪里，点击后谁发请求，结果变化时谁更新界面？父组件通过props把数据交给子组件，组件用state记住会变化的数据；请求、订阅等与外部系统的交互则需要另行安排。我们沿这条数据变化过程理解React。

## 2. 基础知识讲解

### 2.1 组件是接收 props 返回 UI 的函数

```tsx
type CitationProps = {
  sourceId: string;
  quote: string;
  onOpen: (sourceId: string) => void;
};

export function CitationCard({ sourceId, quote, onOpen }: CitationProps) {
  return (
    <li>
      <button type="button" onClick={() => onOpen(sourceId)}>
        打开来源 {sourceId}
      </button>
      <blockquote>{quote}</blockquote>
    </li>
  );
}
```

组件是纯函数：相同 props 渲染相同 UI（忽略外部状态）。不要在渲染中发请求、改全局变量或写 `localStorage`；这些是副作用，放到事件处理器或 `useEffect`。

`children` 是特殊的 props：

```tsx
import type { ReactNode } from "react";

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-labelledby="panel-title">
      <h2 id="panel-title">{title}</h2>
      {children}
    </section>
  );
}
```

`React.ReactNode` 表示可渲染内容；需要 `import type { ReactNode } from "react"` 时用类型导入。不要把 `children` 当成字符串，它可能是元素、数组或 `null`。

### 2.2 state 是组件自己的可变数据

```tsx
import { useState } from "react";

type SearchFormProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function SearchForm({ value, onChange, onSubmit }: SearchFormProps) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim()) onSubmit();
      }}
    >
      <label>
        问题
        <input value={value} onChange={(event) => onChange(event.target.value)} />
      </label>
      <button type="submit" disabled={!value.trim()}>搜索</button>
    </form>
  );
}
```

`useState` 返回当前值和更新函数。更新是**替换**，不是合并：

```tsx
const [filters, setFilters] = useState({ status: "all", user: "" });
setFilters((current) => ({ ...current, status: "paid" })); // 基于最新快照并复制其余字段
```

不要直接 `filters.status = "paid"`；React 看不到可变对象的内部变化，也不会重新渲染。数组同理：用 `map/filter/concat` 生成新数组。

### 2.3 状态放在最近的共同祖先

查询草稿、业务日期和已提交条件属于页面；表单负责提交，列表负责展示。输入尚未提交时不发请求，提交后才把快照交给查询逻辑。重复提交同一条件应能明确刷新，而不依赖React恰好触发effect。

本章第4部分的SearchPage使用同一份输入、提交与结果状态。能由现有值计算出来的条件不另存一份，例如是否允许提交；来源打开通过回调交给已授权的来源入口，不在卡片里猜一个路由。

### 2.4 状态转换还要检查请求归属

只检查loading无法区分A、B两个正在先后执行的请求。开始B后，A的成功回调仍可能抵达。下面的LatestQuery用运行对象标识归属；即使加载器忽略取消，旧完成也不能提交到新状态。previous只在同一key下保留。

<<< ../../typescript-examples/src/query.ts

### 2.5 effect安排启动与退出，结果由运行归属保护

在React中，effect启动当前请求，cleanup使旧运行失效并通知取消。身份、查询或日期变化后，界面先按key隐藏旧结果，不等effect运行才清空。退出不发布卸载后的状态。

读这段源码前先认识四个 Hook：

- `useRef(initial)` 返回跨渲染保持同一引用的可变容器 `{ current }`。改 `current` 不触发渲染；源码用 `loadRef.current = load` 让 effect 不因加载器函数引用变化而重跑，但每次调用都拿最新加载器。
- `useMemo(factory, deps)` 缓存计算结果，依赖不变时返回同一对象。源码用它保持 `LatestQuery` 控制器稳定，避免每次渲染重建运行归属。
- `useCallback(fn, deps)` 缓存函数引用，适合把稳定回调传给子组件或 effect。它不缓存执行结果，也不让函数自动变成“只执行一次”。
- `useId()` 生成组件实例内稳定的唯一 id，用于 `label/htmlFor` 等关联，避免多个搜索表单 id 冲突。

```tsx
const loadRef = useRef(load);
loadRef.current = load;
const controller = useMemo(() => new LatestQuery<string>(setState), []);
const retry = useCallback(() => setAttempt(n => n + 1), []);
const id = useId();
```

边界：`useRef` 适合保存“最新值/外部对象”，不是用来触发界面更新；`useMemo/useCallback` 是引用稳定与性能工具，不是服务端数据缓存，也不能替代请求归属检查。

<<< ../../typescript-examples/src/hooks.ts#query-hook

片段的导入位于[hooks.ts](../../typescript-examples/src/hooks.ts)文件顶部。身份参数描述缓存范围，不代替服务端授权；退出传null，授权或索引版本变化须得到新key。

### 2.6 列表、条件与可访问性

同一来源可能命中多段文字，key不能仅用sourceId:version。样例以来源、版本和引文组成稳定键，保留不同引文。每项只生成一层li，不在li内部再嵌套li。

输入使用label，来源动作用button，结果列表标记“搜索结果”，加载和错误分别使用status/alert。它们也是后续浏览器验收的可访问名称，测试与实际界面应一致。

### 2.7 替换更新与函数式更新对照

`setValue(next)` 使用你这次渲染看到的快照；`setValue(current => next)` 使用 React 即将写入的最新快照。需要基于旧值计算时，用后者。

```tsx
import { useState } from "react";

export function Counter() {
  const [count, setCount] = useState(0);
  return (
    <button type="button" onClick={() => {
      setCount(count + 1);
      setCount(count + 1);
    }}>
      当前计数：{count}
    </button>
  );
}
```

上面代码在**一次点击**里连续执行两次替换更新，预期只显示 `0 → 1`：同一个事件里的两次 `count + 1` 都读取点击前的 `0`，第二次写入的值仍是 `1`。**连续点击两次**才显示 `0 → 1 → 2`，不是 `0 → 2 → 4`。如果只想点击一次就让计数增加2，应写一次 `setCount(count + 2)`；若需要把多次基于旧值的增量累积起来，改成两次 `setCount(current => current + 1)`，一次点击会得到 `2`。

| 更新对象 | 正确形式 | 常见错误 |
| --- | --- | --- |
| 数字计数 | `setCount(current => current + 1)` | 在事件里写 `count += 1` |
| 筛选对象 | `setFilters(current => ({ ...current, status: "paid" }))` | `setFilters({ status: "paid" })` 丢掉 `user` |
| 列表 | `setItems(current => [...current, item])` | `items.push(item)` 后直接更新同一个引用 |
| 可由 props 计算 | 渲染时直接计算 | 用 effect 把派生值再复制进 state |

编译过程：`.tsx` 需要 `jsx: "react-jsx"` 和 React 类型依赖；`pnpm exec tsc --noEmit` 只检查。运行显示依赖 React 渲染，不是普通 Node 脚本输出。常见错误是把函数式更新用于“设置固定值”也无妨，但却在更新函数里修改 `current` 后原样返回，React 会因引用未变跳过渲染。

### 2.8 effect 的启动、重跑与清理对照

```tsx
useEffect(() => {
  const controller = new AbortController();
  void load(query, controller.signal);
  return () => controller.abort();
}, [query, load]);
```

| 情况 | 预期行为 | 必须核对 |
| --- | --- | --- |
| 首次挂载 | setup 启动一次读取 | 返回值是清理函数还是意外 Promise |
| `query` 从 A 变为 B | 先清理 A，再为 B setup | A 的迟到结果被运行归属丢弃 |
| `load` 每次渲染都是新函数 | effect 可能反复重跑 | 调用方用 `useCallback` 稳定引用，或用 ref 保存最新函数 |
| 组件卸载 | 只执行 cleanup，不再 setup | 定时器、监听器、请求都释放 |

不要把 `async` 直接作为 effect 回调：`useEffect(() => async () => {...})` 返回的是 Promise，React 不会把它当 cleanup。应像上面一样在同步函数内启动异步任务，再返回同步清理函数。`[]` 不是“永远不更新”的保证，而是声明 effect 不依赖任何响应式值；若函数体读取了 props/state，就会形成闭包旧值。

## 3. 原理讲解与推导

### 3.1 渲染是状态的快照

一次渲染看到的是当时 state/props 的固定值。事件处理器里的 `state` 也是那次渲染的快照；连续 `setCount(count + 1)` 可能只加一次。需要基于前值更新时用函数式：

```tsx
setCount((current) => current + 1);
```

不要在事件里读一个“稍后会被更新”的变量；React 不保证你在下一次渲染前看到新值。

### 3.2 重渲染不等于重新挂载

state 在组件保持同一位置时保留；条件切换导致组件卸载，state 丢失。把组件定义在另一个组件内部，每次父组件渲染都会创建新组件类型，导致子树重新挂载——这是常见的“输入框失焦/状态丢失”原因。

### 3.3 effect 的双重执行

开发模式下 Strict Mode 可能故意执行 effect 两次，用来暴露缺少清理的副作用。请求要可中止、订阅要退订、定时器要清除；不要用“只跑一次”的标记掩盖问题。

### 3.4 服务端状态与客户端状态

搜索结果、用户资料属于**服务端状态**，有缓存、失效、重新验证；输入框、展开面板属于**客户端状态**。第 9 章会用查询库处理服务端状态；本章先用 `useEffect` 理解基本数据流，不引入额外依赖。

## 4. 示例与逐步走查

以下是已纳入类型检查的组件。load传入已适配的SearchHit[]，来源打开由调用方对接已授权入口；它不是一份绕过后端的检索实现。

<<< ../../typescript-examples/src/search-page.tsx

沿一次提交检查：草稿与业务日期→提交快照→包含主体/租户/授权版本的key→受限请求→只接受当前结果→空、加载、错误或成功。更换身份时，即使旧请求晚到也不能重新显示。

实际React Hook回归在tests/react.test.mjs，使用React DOM与jsdom并开启StrictMode，覆盖旧请求晚到、换租户与退出。jsdom不证明窄屏布局或真实读屏体验，浏览器验收继续在第16章完成。

`SearchPage` 的可观察行为可以逐项验收，不需要猜测组件内部实现：

| 操作/夹具 | 预期界面 |
| --- | --- |
| 首次进入且未提交 | 显示表单，不显示搜索结果 |
| 提交后加载器 pending | 出现 `role="status"` 的“搜索中…” |
| 加载器返回 `[]` | 显示“没有找到相关条款。” |
| 加载器返回两个命中 | `aria-label="搜索结果"` 的列表中有两个 `li` |
| 加载器 `throw new Error("服务不可用")` | `role="alert"` 显示消息，并提供重试按钮 |
| 加载中切换租户 | 立即隐藏旧租户结果；旧回调完成也不能恢复 |
| `identity` 变为 `null` | 显示“请先建立会话。”，数据状态回到 idle |

这些文字来自 `search-page.tsx`。当前 `react.test.mjs` 主要断言 hook 状态与身份隔离；DOM 文案、role 和可访问名称在第16章浏览器验收中核对。修改组件时应同步更新对应 hook 测试或浏览器断言。按钮的 `onClick` 只调用传入的 `onOpenSource(hit)`，不在组件内猜测来源 URL；测试可注入 spy 来核对收到的完整 `SearchHit`。不要把只检查 DOM 节点数量的测试当成授权验证，身份隔离仍要结合服务端权限。

## 5. 练习

### 练习一：跟写

`SearchForm` 已经是受控组件。给它增加“清空”按钮：调用 `onChange("")`，并让父组件重置已提交条件与搜索结果；确认清空后没有残留旧数据。

### 练习二：改造

阅读 `stream-state.ts` 的 `AnswerState`：它已有 `streaming` 分支并携带 `text` 和 `citations`。给它设计一个 `tools` 待复核分支（携带工具调用与状态），说明为什么不能只加一个 `isStreaming` 布尔值；再写出 reducer 需要新增的动作。

### 练习三：独立

实现 `useSearch` 自定义 hook：输入 `query`/`apiBaseUrl`，返回 `state` 和 `retry`。要求请求可中止、错误可重试、快速输入不产生竞态；为它写一个不依赖浏览器的 reducer 测试。

## 6. 验收与自测

**行为验收：** 快速修改查询不会显示旧结果；卸载后请求中止；空/加载/错误/成功四态互斥；列表 key 稳定；表单有 label，错误可被读屏识别。

**原理验收：** 能解释 state 快照、批处理、`useEffect` 清理、重渲染与重新挂载的差异；能说出一个“把服务端状态塞进客户端 state”的坏处。

### 6.1 先预测，再查看解释

在 `useEffect` 中发请求但不返回清理函数，快速把查询从 A 改成 B，可能出现什么？

<details>
<summary>完成预测后查看解释</summary>

A可能在B之后返回。取消控制资源等待，运行归属控制谁可以更新状态；两者一起使用。只忽略AbortError或只检查loading，都没有区分A和B。

</details>

## 7. 面试问答与参考回答

**问：props 和 state 的区别？**

props 由父组件传入，组件只读；state 由组件自己拥有，通过更新函数触发重渲染。能由 props 计算的值不要再存 state，避免两份数据不同步。

**问：为什么不能直接修改 state 对象？**

React 用引用比较判断是否变化；原地修改不会产生新引用，可能不重渲染，也会破坏历史快照。用展开、`map`、`filter` 创建新对象/数组。

**问：`useEffect` 的依赖数组怎么写？**

包含 effect 读取的所有响应式值；漏依赖会读旧值，多写不必要依赖会频繁重跑。清理函数负责取消请求、退订和清定时器；Strict Mode 双执行是检查清理的机会。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 一次搜索提交后，这一帧看到的是哪份 state，晚到的旧请求结果还能不能写回界面？

**一条主线：**

```text
props/state → 渲染快照 → 事件更新（替换而非原地改）→ effect 启停与 cleanup → 运行归属检查 → 新界面
```

**三个关键词：** 快照、归属、清理。渲染是状态的快照，运行归属决定哪个请求能提交结果，cleanup 让旧运行失效并取消请求。

**最容易错：**

- 直接改 `filters.status`，或用数组下标当 key，React 看不到变化、列表状态错位。
- 在渲染里发请求、写 `localStorage`：组件应是 props 到 UI 的纯函数，副作用放事件处理器或 effect。
- 只检查 `loading` 就相信结果，A 的迟到回调覆盖 B；只 cancel 不做归属检查同样不行。
- 漏 effect 依赖或没有 cleanup，Strict Mode 双执行时才暴露重复请求和定时器泄漏。

**与前后章：** 上一章的包边界让组件和 hooks 能按模块导入；下一章需要把请求、缓存、失效和错误隔离从组件里抽成查询 hook。

**学完应能：**

- 把搜索页拆成表单、结果列表和引用卡片，用判别联合或 reducer 表达空、加载、错误、成功四态，状态放在最近共同祖先、能算出的值不另存；
- 用 `LatestQuery` 的运行标识加 `AbortController`，让旧请求无法覆盖新身份；
- 解释 state 快照、重渲染和重新挂载的差别，并复现一次输入框失焦；
- 给列表用来源、版本、引文组成的稳定 key，让错误能被读屏识别。

### 8.2 参考与后续学习

参考：[React: Describing the UI](https://react.dev/learn/describing-the-ui)、[Managing State](https://react.dev/learn/managing-state)、[Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects)。

[上一章](07-模块构建与工程化.md) · [全书目录](教材目录.md) · [第 9 章](09-异步数据缓存与错误边界.md)
