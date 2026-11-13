# 附录D　JavaScript 与浏览器基础：从 Java 后端到前端

[第5章](05-异步并发与取消.md) · [第8章](08-React组件与状态.md) · [第10章](10-流式AI界面.md) · [全书目录](教材目录.md)

这不是另一套前端课程，而是读第5、8、10章之前需要的最小底座。目标不是背 API，而是能回答：

- 一个函数在 JS 里为什么能作为值传来传去？
- `await` 到底暂停了什么，什么还在继续跑？
- 浏览器里的“请求 → DOM → 重渲染”是怎样一条链？
- 从无框架页面迁移到 React，组件、props、state、effect 各解决什么问题？
- 快速提交两次时，旧响应为什么可能覆盖新结果？

## 1. 对象、函数与闭包

Java 后端熟悉“类 + 方法”；JS 更常见“对象字面量 + 函数值”。

```js
const order = { id: "A", cents: 1990 };
const format = cents => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;

console.log(format(order.cents)); // 19.90
```

函数是值，可以放进对象、作为参数、从函数返回：

```js
function makeLimit(maxCents) {
  return amount => amount <= maxCents;
}

const small = makeLimit(10000);
const large = makeLimit(100000);
console.log(small(20000), large(20000)); // true false
```

`small` 和 `large` 各自保留 `maxCents` 的绑定。和 Python 闭包一样：捕获的是绑定/cell，不是值快照；不要用“函数返回后变量就没了”解释。

### 对象复制仍是浅复制

```js
const original = { id: "A", tags: ["new"] };
const copy = { ...original };
copy.tags.push("paid");
console.log(original.tags); // ["new", "paid"]
```

展开只复制第一层。要独立复制嵌套结构，需要逐层复制或使用结构化克隆；但不是所有对象都能克隆（函数、DOM 节点、连接等）。

## 2. 模块：先明确边界，再谈打包

```js
// money.js
export function formatCents(cents) { /* ... */ }

// page.js
import { formatCents } from "./money.js";
```

- `export` 暴露公共接口，`import` 建立依赖；
- 浏览器用 URL 加载模块，Node 用文件路径；
- 打包器（Vite/esbuild）负责把模块图变成浏览器可加载的产物；
- 不要用全局变量在模块间传数据，否则测试和加载顺序会互相影响。

## 3. Promise、async/await 与事件循环

```js
async function loadOrder(id) {
  const response = await fetch(`/api/orders/${id}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
```

`await` 不是“阻塞整个浏览器”，而是暂停当前 async 函数，把控制权交回事件循环；其他任务（点击、计时器、其他请求）仍可运行。

### 三个必须分开的概念

| 概念 | 作用 |
| --- | --- |
| Promise | 表示一次未来结果，可成功/失败 |
| `await` | 在 async 函数内等待 Promise，暂停这个函数 |
| 事件循环 | 调度已完成的回调/微任务；不保证“先发先回” |

```js
console.log("A");
setTimeout(() => console.log("B"), 0);
Promise.resolve().then(() => console.log("C"));
console.log("D");
// A D C B
```

微任务（Promise 回调）先于宏任务（setTimeout）执行；不要用“谁先写的代码谁先跑”解释异步顺序。

### 并发与取消

```js
const controller = new AbortController();
const promise = fetch("/api/search", { signal: controller.signal });
controller.abort(); // 请求被取消，promise 以 AbortError 拒绝
```

- 取消是请求，不保证服务端已经停止；
- 已经收到的数据、已经发生的副作用要单独处理；
- 每次请求使用自己的 controller，不要让两次请求共享一个信号。

## 4. 浏览器：请求、DOM 与渲染

```js
const form = document.querySelector("#search-form");
const output = document.querySelector("#results");

form.addEventListener("submit", async event => {
  event.preventDefault();
  const query = new FormData(form).get("q");
  output.textContent = "搜索中…";
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: query }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    output.textContent = data.items.length ? `${data.items.length} 条结果` : "没有结果";
  } catch {
    output.textContent = "检索暂不可用";
  }
});
```

要点：

- 表单提交要 `preventDefault()`，否则页面刷新；
- 用 `textContent` 渲染用户/模型文本，不用 `innerHTML` 拼接；
- 加载、空结果、错误是三种不同状态，不能都显示空白；
- 键盘提交、`label` 关联、`role="status"`/`role="alert"` 是可访问性的最低要求。

### 同源、代理、CORS 与 Cookie

- 浏览器默认限制跨源读取响应；开发时常用 Vite/Node 代理把 `/api` 转到 BFF，保持同源；
- CORS 是浏览器行为，不是服务端鉴权；
- Cookie 需要 `HttpOnly`、`Secure`、`SameSite` 等属性；不要把 token 放进 `localStorage` 当作默认方案；
- 前端不直接持有模型密钥，也不直接访问 Python 内部地址。

## 5. 从无框架页面到 React

无框架页面直接操作 DOM：查询元素、绑事件、改文本。页面变大后，状态散落在 DOM 和闭包里，容易出现“显示与数据不一致”。

React 把页面描述成“状态 → UI”：

```tsx
function SearchBox({ onSearch }: { onSearch: (q: string) => void }) {
  const [draft, setDraft] = useState("");
  return <form onSubmit={e => { e.preventDefault(); if (draft.trim()) onSearch(draft.trim()); }}>
    <label htmlFor="q">问题</label>
    <input id="q" value={draft} onChange={e => setDraft(e.target.value)} />
    <button type="submit">搜索</button>
  </form>;
}
```

| 概念 | 解决什么 |
| --- | --- |
| 组件 | 把 UI 与行为封装成可复用单元 |
| props | 父组件传给子组件的只读输入 |
| state | 组件自己会变化、需要触发重渲染的数据 |
| effect | 与外部系统同步（请求、订阅、定时器），并负责清理 |
| key | 列表项身份；不要用数组下标代替稳定 ID |

迁移时先保留同一组状态：`idle/loading/success/empty/error`；不要一边换框架一边换业务契约。

## 6. 一次完整的数据竞争分析

请求 A 先发、后回；请求 B 后发、先回。如果 A 的回调直接写结果，它会把 B 的结果覆盖。

```js
let current = 0;
async function search(query) {
  const ticket = ++current;
  const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  const data = await response.json();
  if (ticket !== current) return; // 旧请求不能写当前页面
  render(data);
}
```

React 中还要处理组件卸载、身份切换、StrictMode 的双重 effect。原则：

1. 每次请求有独立 `AbortController`；
2. 响应回来先检查“是否仍是当前请求/当前身份”；
3. 取消不保证底层停止，UI 要保留已收到内容或明确失败；
4. 旧请求的 catch 不能清空新请求的缓冲。

## 7. 练习：给搜索页加一个筛选条件

在现有 `SearchPage` 或最小宿主上增加“来源类型”筛选：

- 表单增加一个 `select`，与问题、日期一起提交；
- 接口增加可选字段，BFF 校验并转发；不要只在前端过滤已返回结果；
- 状态增加 `filter`，切换时取消旧请求；
- 空结果、错误、加载中分别显示；
- 用键盘操作一遍，确认 label 和焦点可见；
- 模拟 A 慢、B 快，确认 B 的结果不会被 A 覆盖。

验收不是“类型检查通过”，而是：

```text
新筛选能改变请求参数；
快速切换两次，页面只显示最后一次；
清空筛选后旧结果不残留；
错误后可重试；
来源详情仍能打开且版本正确。
```

## 8. 和教材章节的对应

| 本附录 | 对应章节 |
| --- | --- |
| 对象/函数/闭包/模块 | 第1–4、7章 |
| Promise/事件循环/取消 | 第5章 |
| 浏览器请求/DOM/表单 | 第6、8章；B+ 最小页面 |
| React 状态/effect/key | 第8–10章 |
| 数据竞争/取消归属 | 第8–10章；`useAsyncData`、`LatestQuery` |
| 可访问性/错误反馈 | 第8、10、16章 |

读完附录不等于前端专家；它保证你能读懂并改造本书的页面、请求和状态，不把“类型通过”当成前端完成。