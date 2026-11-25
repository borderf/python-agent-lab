# 第12章　SQL、Drizzle 与事务

[上一章](11-Hono-BFF.md) · [全书目录](教材目录.md) · [下一章](13-认证多租户与权限.md)

## 1. 学习目标与前置知识

能设计订单/文档表的键与索引，用 SQL 和 Drizzle 写查询、插入、冲突处理与事务，能在 SQLite 本地开发后迁移到 PostgreSQL，能解释 ORM 不自动解决的边界。前置：第 11 章；会 SQL 与 Spring `@Transactional` 更佳。

**本章从这里开始：** 内存仓储重启就丢；直接拼 SQL 会注入；`insert` 重复导入报唯一冲突；审批写一半失败，数据库留下半条记录。BFF 要持久化，就必须回答：键是什么、事务到哪、冲突怎么处理、SQLite 和 PostgreSQL 差在哪。

## 2. 基础知识讲解

### 2.1 先画表，再选 ORM

文档表的业务键不是自增 ID，而是 `(tenant_id, source_id, version)`：

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  UNIQUE (tenant_id, source_id, version)
);
```

唯一约束保证同一租户、同一来源、同一版本只有一条；索引支持按租户和有效期查询：

```sql
CREATE INDEX documents_lookup
  ON documents (tenant_id, source_id, valid_from);
```

Java/JPA 常从实体注解生成表；TypeScript 侧更常见“schema 是源，类型由 schema 推出”。两种都可以，但迁移脚本必须能审查，不能只靠 `synchronize: true`。

### 2.2 同一份schema与仓储

主线的文档事实仍由Python维护。本章是TS数据库专项，不同时向两份业务库双写。为了让Windows与CI不依赖原生扩展编译，配套使用真实SQLite WASM（sql.js）和Drizzle；它不是假仓储。

<<< ../../typescript-examples/src/documents.ts

### 2.3 查询先表达半开区间

条件是valid_from <= asOf，且valid_to为空或valid_to > asOf。Drizzle以列/SQL表达式作为比较左操作数，所以使用gt(documents.validTo, asOf)。不能把普通字符串放在lt的左侧。

日期先在入口规范成ISO文本。数据库条件同时限定租户；测试检查valid_to前一天、当天，以及另一租户。

### 2.4 重复与冲突分开处理

业务键是租户、来源、版本。INSERT由唯一约束决定是否冲突；同键同内容返回原id，同键改内容拒绝，不执行静默更新。物理id与逻辑版本身份是不同概念。

返回行先解构为inserted，再判断对象是否存在；数组length > 0不会普遍收窄noUncheckedIndexedAccess下的inserted[0]。

### 2.5 批量原子性与驱动边界

配套同步SQLite事务中，第2条发生版本冲突时，前面的新插入也回滚。sql.js导出二进制可重新载入，用来验证本地存储边界；它不证明磁盘写入、网络存储或PostgreSQL隔离保证。

迁移到better-sqlite3或PostgreSQL时保留业务契约，另接对应驱动与持久化。同步事务中不等待网络；PostgreSQL的异步回调、隔离与重试需在真实环境另测。

### 2.6 SQLite 到 PostgreSQL

| 主题 | SQLite | PostgreSQL |
| --- | --- | --- |
| 自增 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `GENERATED ... AS IDENTITY` |
| 时间 | `TEXT` ISO | `timestamptz` |
| 布尔 | 0/1 | `boolean` |
| JSON | `TEXT`/JSON1 | `jsonb` |
| 冲突 | `ON CONFLICT` | `ON CONFLICT` |
| 返回 | 有限支持 `RETURNING` | 完整 `RETURNING` |
| 并发 | 单写者为主 | MVCC、行锁、隔离级别 |

本地 SQLite 适合教学和单机；部署到多用户服务要评估 PostgreSQL。迁移时先改 schema 与查询，再跑同一组契约测试；不要假设 SQLite 的行为等于 PostgreSQL。

### 2.7 分页与索引

选读：给专项schema显式新增created_at并定义排序后，再考虑keyset。下面是设计SQL，不是当前未加该字段的表可直接执行的查询：

```sql
SELECT * FROM documents
WHERE tenant_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

索引要匹配查询的过滤和排序：`(tenant_id, created_at, id)`。不要给每一列都建索引；写入也会变慢。

### 2.8 最小例子：插入、重复与半开区间

下面只使用配套已有的`sql.js`和Drizzle，不引入新驱动。`satisfies NewDocument`在编译期检查字段，同时保留具体字面量；运行时是否合法仍由数据库约束和调用入口负责。

```ts
import { createDocumentStore, type NewDocument } from "./documents.js";

const store = await createDocumentStore();
const row = {
  id: "d1", tenantId: "a", sourceId: "policy-a", version: "1",
  title: "付款制度", body: "预付款20%",
  validFrom: "2026-01-01", validTo: "2026-07-01",
} satisfies NewDocument;

try {
  console.log(store.insert(row));
  console.log(store.insert({ ...row, id: "retry-id" }));
  console.log(store.visible("a", "2026-06-30").map(item => item.title));
  console.log(store.visible("a", "2026-07-01").length);
} finally {
  store.close();
}
```

按当前实现推导，输出应为：

```text
{ status: 'inserted', id: 'd1' }
{ status: 'duplicate', id: 'd1' }
[ '付款制度' ]
0
```

第二插入虽然物理id写成retry-id，但业务键相同、内容相同，所以返回原id，不新建行。6月30日可见，7月1日是valid_to，半开区间不再包含它。这里只列预期，不把未执行的文档片段写成实测输出。

### 2.9 插入三态与错误边界

| 输入情况 | 数据库发生什么 | 当前返回/抛出 | 调用方应做什么 |
| --- | --- | --- | --- |
| 业务键不存在 | INSERT成功 | `{status:"inserted", id:新id}` | 继续事务或返回201语义 |
| 业务键存在且title/body/有效期相同 | `ON CONFLICT DO NOTHING`无插入 | `{status:"duplicate", id:原id}` | 视为已处理，保留原身份 |
| 业务键存在但任一事实字段不同 | 不覆盖，随后检测冲突 | 抛`同一来源/版本内容冲突` | 在当前专项按冲突处理；HTTP层另映射409 |
| id重复但业务键不同 | 主键冲突，当前实现未单独分类 | 抛出数据库错误 | 不要一律翻译成“版本冲突” |
| valid_to <= valid_from | CHECK拒绝 | 抛出约束错误 | 入口先校验，持久层再兜底 |

“同内容”比较包含title、body、validFrom、validTo，不包含物理id；修改title也可能改变证据呈现，因此不能静默覆盖。当前`insert`没有返回结构化错误码，若开放HTTP路由，需要把唯一键冲突、主键冲突、CHECK失败分别映射，不能把所有异常都当409。

### 2.10 事务边界与常见错误

`importBatch(rows)`把`rows.map(insert)`放进`db.transaction`。第2条检测到内容冲突并抛错时，Drizzle回滚第1条插入。因此验收必须重新查询“第1条也不存在”，不能只断言抛错。

当前sql.js适配是同步事务：回调不能`await`网络或模型。PostgreSQL驱动通常异步，不能把同步回调原样搬过去，也不能认为SQLite的单写者行为等于PostgreSQL的MVCC/行锁。

| 常见错误 | 结果 | 正确做法 |
| --- | --- | --- |
| 先select再insert判重 | 并发双插 | 唯一约束+冲突处理，应用查询只改善提示 |
| 把valid_to比较写成`>=` | 失效当天仍可见 | 使用`gt(validTo, asOf)` |
| 只按sourceId/version去重 | 跨租户误判重复 | 业务键包含tenantId |
| 批量中catch每条错误后继续 | 留下半批事实 | 让异常退出transaction，整批回滚 |
| 在事务回调里await HTTP | 同步驱动不会提供原子外部效果 | 本地账本+稳定动作键+对账 |

## 3. 原理讲解与推导

### 3.1 ORM 不代替 SQL

Drizzle 让查询有类型，但不会自动选对索引、不会替你决定事务边界、不会阻止 N+1。Java/JPA 也一样。先写 SQL 和 `EXPLAIN`，再用 ORM 表达；复杂报表可以直接 SQL。

### 3.2 唯一约束是并发下的最后防线

“先查再插”在并发下会竞态；唯一约束 + `ON CONFLICT` 才能在数据库层保证唯一。应用层检查用于友好错误，数据库约束用于正确性。

### 3.3 事务与外部效果

数据库事务不能回滚已经调用的模型/HTTP 写入。需要“动作键 + 本地账本 + 对账”，而不是把外部调用包进 `BEGIN`。第 14 章会把审批/写入接到 BFF 时再展开。

### 3.4 查询、约束、事务各自保证什么

半开查询`tenantId=a AND validFrom<=asOf AND (validTo IS NULL OR validTo>asOf)`由`and/lte/or/isNull/gt`组合。Drizzle把这些SQL表达式绑定到列，参数asOf作为值传入；这不是字符串拼接，也不会让asOf变成列名。

| 机制 | 保证 | 不保证 |
| --- | --- | --- |
| WHERE租户条件 | 这次查询不返回其他租户行 | 调用方没有绕过repository |
| UNIQUE业务键 | 并发下不能存在两条同键事实 | 同键内容是否语义一致 |
| 冲突后比较 | 相同重试返回原id，不同内容拒绝 | 外部导出/通知没有重复 |
| transaction | 本地这批SQL全提交或全回滚 | 进程崩溃后的存储、外部HTTP、PostgreSQL隔离 |
| export/reopen | 当前SQLite二进制可重载并读到数据 | 磁盘fsync、网络存储、生产备份 |

索引让查询更快，但不改变结果正确性；唯一约束保证正确性，但不替代冲突提示；事务保证本地原子性，但不涵盖外部副作用。

## 4. 示例与逐步走查

运行同一套SQLite契约：

```powershell
pnpm --dir typescript-examples test
```

integration.test.mjs检查新插入、同键重复、同版本冲突、半开日期、另一租户、批量回滚和导出后重开。先预测每种结果，再在练习副本删除一个关键条件，确认相应测试变红。

HTTP请求仍按第11章在可信身份下校验，不把unknown断言成NewDocument。当前专项没有开放文档上传路由；扩展时要把输入值域、日期与角色检查放在真实入口，不能把所有数据库错误都翻译成409。

### 4.1 用结果表检查查询，而不是看代码“像对的”

`integration.test.mjs`把同一行数据放入三个范围：asOf为valid_to前一天、当天、另一租户。预期分别是1、0、0；再把同键同内容重插、同键异内容插入，预期duplicate和冲突。批量用例则先放一条已存在行，再导入“新行+同键异内容”，异常后查询原范围，确认新行没有留下。

导出后重新`createDocumentStore(store.export())`只能证明这份WASM数据库字节可重载。它没有写磁盘，也没有模拟两个进程同时提交；不要据此写“持久化文件和并发锁已验证”。

## 5. 练习

### 5.1 跟写

给 `documents` 增加 `(tenant_id, valid_from, valid_to)` 索引，用 `EXPLAIN QUERY PLAN` 验证查询使用索引。

### 5.2 改造

`integration.test.mjs` 已覆盖新插入、同键同内容重插、同键异内容冲突，以及 `valid_to` 当天不可见。本节改造不重复已有断言，改为补一条尚未覆盖的边界：新增一条只导入单文档的入口 `insertDocument(document)`，复用 `importBatch([document])` 的校验与事务，使调用方无需先构造数组；然后验证新插入、重复相同、重复不同、以及把已有文档的 `valid_to` 设为查询日期后不可见。重复不同必须抛冲突，不能覆盖同版本内容。

### 5.3 独立

实现批量导入事务：一批 10 条，第 5 条违反唯一约束时整批回滚；记录失败行号，不留下半批数据。再把 schema 迁到 PostgreSQL，跑同一组测试。

## 6. 验收与自测

**行为验收：** 当前SQLite专项的租户、日期、版本冲突、事务回滚与重开检查通过。分页和PostgreSQL迁移是扩展，只有在实际实现并运行后才写通过。

**原理验收：** 能解释唯一约束与先查后插的竞态、事务与外部效果的区别、SQLite/PostgreSQL 的关键差异。

| 操作 | 预期 | 现有证据 |
| --- | --- | --- |
| 插入新业务键，再以不同物理id重插同内容 | inserted→duplicate，最终1行且id不变 | `integration.test.mjs`SQLite用例 |
| 同键修改body | 抛冲突，原文不被覆盖 | 同上`assert.throws(/冲突/)` |
| 查valid_to前一天/当天/另一租户 | 行数1/0/0 | 同上三个visible断言 |
| 批量第2条冲突 | 抛错且第1条也查询不到 | 批量回滚用例重新查visible |
| export后用新store载入 | 仍读到同一body | 重开用例 |
| 迁移PostgreSQL后重跑 | 结果契约一致，另记录隔离/锁差异 | 当前未实现，不能填通过 |

“现有证据”指测试源码中的断言；本章修改文档没有重新执行它们。实际交付时应附命令、退出码和关键输出。

### 6.1 先预测，再查看解释

两个请求同时导入同一 `(tenant, source, version)`，应用层“先查再插”能保证唯一吗？

<details>
<summary>完成预测后查看解释</summary>

不能。两个请求可能同时查到“不存在”，然后都插入。必须依赖数据库唯一约束和 `ON CONFLICT`/捕获冲突；应用层检查只用于提前给出友好错误，不是并发正确性的保证。

</details>

## 7. 面试问答与参考回答

**问：ORM 能代替 SQL 吗？**

不能。ORM 帮你映射和组合查询，但不自动优化索引、事务边界和 N+1。复杂查询、报表和性能问题仍要看 SQL 与执行计划。

**问：唯一约束和唯一索引有什么区别？**

多数数据库用唯一索引实现唯一约束；约束表达业务规则，索引提供执行结构。并发下靠数据库唯一性，不靠应用层先查后插。

**问：SQLite 能直接用于生产吗？**

单机、低并发、嵌入式可以；多用户服务要考虑写并发、备份、迁移和运维。教学先用 SQLite，部署前评估 PostgreSQL。

## 8. 本章小结与参考

### 8.1 一页知识地图

**本章主问题：** 数据搬进数据库后，怎样用键、约束、事务和迁移保证同一份事实只有一份、半途失败不留半条？

**一条主线：**

```text
业务键 + 半开有效期
→ 唯一约束/冲突策略 + 事务 + 驱动适配
→ 可重开、可迁移的持久事实
```

**三个关键词：** 业务键、唯一约束、事务边界。业务键定义“同一条”，约束处理并发判重，事务保证这批本地SQL全成或全败。

**最容易错：**
- 先查后插、闭区间有效期、跨租户漏过滤、同键异内容静默覆盖。
- 只断言批量抛错，不查前半批是否回滚；把export/reopen当磁盘或PostgreSQL验证。
- 在同步sql.js事务里await外部调用；把所有数据库异常映射成409。

**与前后章：** 第11章提供可信身份与校验；第13章把Actor的租户/角色贯彻到每条读写和对象级授权。

**学完应能：** 从插入三态、半开区间和批量回滚推导结果；指出当前SQLite证据与生产数据库证据的边界。

### 8.2 参考与后续学习

参考：[Drizzle ORM](https://orm.drizzle.team/docs/overview)、[SQLite](https://www.sqlite.org/docs.html)、[PostgreSQL](https://www.postgresql.org/docs/)。

[上一章](11-Hono-BFF.md) · [全书目录](教材目录.md) · [下一章](13-认证多租户与权限.md)
