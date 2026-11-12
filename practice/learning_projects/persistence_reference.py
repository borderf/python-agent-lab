"""Small-corpus persistence adapter around an injected learner RAG core.

Each query rebuilds an index from the tenant's committed documents. This is a
deliberate correctness baseline, not an incremental/vector index design.
"""
from contextlib import closing
import json
import sqlite3


def _connect(db_path):
    db = sqlite3.connect(db_path, timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS documents (tenant_id TEXT, source_id TEXT, "
               "version TEXT, content TEXT NOT NULL, PRIMARY KEY(tenant_id, source_id, version))")
    return db


def put_document(db_path, raw, *, core):
    document = core.normalize_document(raw)
    key = tuple(document[name] for name in ("tenant_id", "source_id", "version"))
    content = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with closing(_connect(db_path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT content FROM documents WHERE tenant_id=? AND source_id=? AND version=?",
                         key).fetchone()
        if old:
            if old[0] != content:
                raise ValueError("same source version has different content")
            return False
        db.execute("INSERT INTO documents VALUES (?, ?, ?, ?)", (*key, content))
    return True


def _index(db_path, tenant_id, core):
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("trusted tenant_id is required")
    with closing(_connect(db_path)) as db:
        rows = db.execute("SELECT content FROM documents WHERE tenant_id=? ORDER BY source_id, version",
                          (tenant_id,)).fetchall()
    return core.build_index([json.loads(row[0]) for row in rows])


def search(db_path, question, *, tenant_id, as_of, core):
    return core.search(_index(db_path, tenant_id, core), question, tenant_id=tenant_id, as_of=as_of)


def answer(db_path, question, *, tenant_id, as_of, core, model):
    return core.answer(_index(db_path, tenant_id, core), question, tenant_id=tenant_id,
                       as_of=as_of, model=model)
