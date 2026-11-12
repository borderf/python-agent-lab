import { createRequire } from "node:module";
import initSqlJs from "sql.js";
import { drizzle } from "drizzle-orm/sql-js";
import { sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";
import { and, asc, eq, gt, isNull, lte, or } from "drizzle-orm";

export const documents = sqliteTable("documents", {
  id: text("id").primaryKey(), tenantId: text("tenant_id").notNull(), sourceId: text("source_id").notNull(),
  version: text("version").notNull(), title: text("title").notNull(), body: text("body").notNull(),
  validFrom: text("valid_from").notNull(), validTo: text("valid_to"),
}, table => [uniqueIndex("source_version").on(table.tenantId, table.sourceId, table.version)]);
export type NewDocument = typeof documents.$inferInsert;

// 真实SQLite WASM + Drizzle；默认内存库，可导出二进制后重新加载。
// 这是TS数据库专项，主线文档事实仍由Python服务维护，不做两边业务双写。
export async function createDocumentStore(bytes?: Uint8Array) {
  const require = createRequire(import.meta.url);
  const SQL = await initSqlJs({ locateFile: file => require.resolve(`sql.js/dist/${file}`) });
  const sqlite = new SQL.Database(bytes);
  sqlite.run(`CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, source_id TEXT NOT NULL, version TEXT NOT NULL,
    title TEXT NOT NULL, body TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
    UNIQUE(tenant_id, source_id, version), CHECK(valid_to IS NULL OR valid_to > valid_from))`);
  const db = drizzle(sqlite);
  function insert(row: NewDocument) {
    const [inserted] = db.insert(documents).values(row).onConflictDoNothing({
      target: [documents.tenantId, documents.sourceId, documents.version],
    }).returning({ id: documents.id }).all();
    if (inserted) return { status: "inserted" as const, id: inserted.id };
    const existing = db.select().from(documents).where(and(eq(documents.tenantId, row.tenantId),
      eq(documents.sourceId, row.sourceId), eq(documents.version, row.version))).get();
    if (existing && existing.title === row.title && existing.body === row.body
        && existing.validFrom === row.validFrom && existing.validTo === (row.validTo ?? null)) {
      return { status: "duplicate" as const, id: existing.id };
    }
    throw new Error("同一来源/版本内容冲突");
  }
  return {
    insert,
    importBatch(rows: NewDocument[]) { return db.transaction(() => rows.map(insert)); },
    visible(tenant: string, asOf: string) {
      return db.select().from(documents).where(and(eq(documents.tenantId, tenant), lte(documents.validFrom, asOf),
        or(isNull(documents.validTo), gt(documents.validTo, asOf)))).orderBy(asc(documents.id)).all();
    },
    export: () => sqlite.export(), close: () => sqlite.close(),
  };
}
