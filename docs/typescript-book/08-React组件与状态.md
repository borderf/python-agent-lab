# 第08章　React 组件、状态与数据流

[上一章](07-模块构建与工程化.md) · [全书目录](教材目录.md) · [下一章](09-异步数据缓存与错误边界.md)

## 1. 学习目标与前置知识

能把界面拆成组件，用 props 传数据、用 state 表达变化，用判别联合表示加载/流式/完成/失败，用 `useEffect` 同步外部资源并在卸载时清理。前置：第 1–7 章；会 JavaScript/TS 函数与对象；DOM/React 基础不熟先读[附录D](附录D-JavaScript与浏览器基础.md)。

**本章从这里开始：** 搜索框、结果列表、回答卡片、引用和错误提示如果都塞进一个组件，状态会互相污染；如果每个小组件都自己发请求，又会出现重复请求和竞态。React 的核心不是“组件语法”，而是**数据流**：谁拥有状态，谁只接收 props，副作用在哪里发生。

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
setFilters({ ...filters, status: "paid" }); // 必须复制其余字段
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

<<< ../../typescript-examples/src/hooks.ts#query-hook

片段的导入位于[hooks.ts](../../typescript-examples/src/hooks.ts)文件顶部。身份参数描述缓存范围，不代替服务端授权；退出传null，授权或索引版本变化须得到新key。

### 2.6 列表、条件与可访问性

同一来源可能命中多段文字，key不能仅用sourceId:version。样例以来源、版本和引文组成稳定键，保留不同引文。每项只生成一层li，不在li内部再嵌套li。

输入使用label，来源动作用button，结果列表标记“搜索结果”，加载和错误分别使用status/alert。它们也是后续浏览器验收的可访问名称，测试与实际界面应一致。

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

## 5. 练习

### 练习一：跟写

把 `SearchForm` 改成受控组件，增加“清空”按钮；清空时同时重置搜索结果，确认没有残留旧数据。

### 练习二：改造

给 `SearchState` 增加 `streaming` 分支（带 `text` 和 `citations`），让回答区能边收边显示；说明为什么不能只加一个 `isStreaming` 布尔值。

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
