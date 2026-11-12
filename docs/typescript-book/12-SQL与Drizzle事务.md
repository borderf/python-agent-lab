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

## 3. 原理讲解与推导

### 3.1 ORM 不代替 SQL

Drizzle 让查询有类型，但不会自动选对索引、不会替你决定事务边界、不会阻止 N+1。Java/JPA 也一样。先写 SQL 和 `EXPLAIN`，再用 ORM 表达；复杂报表可以直接 SQL。

### 3.2 唯一约束是并发下的最后防线

“先查再插”在并发下会竞态；唯一约束 + `ON CONFLICT` 才能在数据库层保证唯一。应用层检查用于友好错误，数据库约束用于正确性。

### 3.3 事务与外部效果

数据库事务不能回滚已经调用的模型/HTTP 写入。需要“动作键 + 本地账本 + 对账”，而不是把外部调用包进 `BEGIN`。第 14 章会把审批/写入接到 BFF 时再展开。

## 4. 示例与逐步走查

运行同一套SQLite契约：

```powershell
pnpm --dir typescript-examples test
```

integration.test.mjs检查新插入、同键重复、同版本冲突、半开日期、另一租户、批量回滚和导出后重开。先预测每种结果，再在练习副本删除一个关键条件，确认相应测试变红。

HTTP请求仍按第11章在可信身份下校验，不把unknown断言成NewDocument。当前专项没有开放文档上传路由；扩展时要把输入值域、日期与角色检查放在真实入口，不能把所有数据库错误都翻译成409。

## 5. 练习

### 5.1 跟写

给 `documents` 增加 `(tenant_id, valid_from, valid_to)` 索引，用 `EXPLAIN QUERY PLAN` 验证查询使用索引。

### 5.2 改造

把 `importDocument` 的版本冲突测试补齐：新插入、重复相同、重复不同三种情况；重复不同必须抛冲突，不能覆盖同版本内容。再写一个测试验证 `valid_to` 当天不再可见（`asOf == valid_to` 返回空）。

### 5.3 独立

实现批量导入事务：一批 10 条，第 5 条违反唯一约束时整批回滚；记录失败行号，不留下半批数据。再把 schema 迁到 PostgreSQL，跑同一组测试。

## 6. 验收与自测

**行为验收：** 当前SQLite专项的租户、日期、版本冲突、事务回滚与重开检查通过。分页和PostgreSQL迁移是扩展，只有在实际实现并运行后才写通过。

**原理验收：** 能解释唯一约束与先查后插的竞态、事务与外部效果的区别、SQLite/PostgreSQL 的关键差异。

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

- 先设计键、唯一约束和索引，再选 ORM。
- 查询必须带租户过滤；日期/版本条件写清边界。
- 插入用唯一约束 + 冲突策略；事务覆盖业务单元。
- SQLite 本地开发，PostgreSQL 部署；用同一组契约测试迁移。

参考：[Drizzle ORM](https://orm.drizzle.team/docs/overview)、[SQLite](https://www.sqlite.org/docs.html)、[PostgreSQL](https://www.postgresql.org/docs/)。

[上一章](11-Hono-BFF.md) · [全书目录](教材目录.md) · [下一章](13-认证多租户与权限.md)
