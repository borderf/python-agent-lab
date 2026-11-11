"""Local SQLite receiver demonstrating one durable effect per scoped key.

This does not implement real authentication, approval issuance, or distributed
exactly-once delivery. The approval hash is trusted input to this boundary.
"""

from contextlib import closing
import hashlib
import json
import sqlite3
from uuid import uuid4


def payload_hash(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def submit(db_path, *, tenant_id, action_id, payload, approved_hash, fail_after_commit=False):
    if not isinstance(tenant_id, str) or not tenant_id.strip() or not isinstance(action_id, str) or not action_id.strip():
        raise ValueError("tenant and action IDs are required")
    digest = payload_hash(payload)
    if digest != approved_hash:
        raise PermissionError("approval does not match payload")
    with closing(sqlite3.connect(db_path, timeout=5)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS effects (tenant_id TEXT, action_id TEXT, "
                   "payload_hash TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(tenant_id, action_id))")
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload_hash, receipt FROM effects WHERE tenant_id=? AND action_id=?",
                             (tenant_id, action_id)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("action key reused with changed payload")
                receipt = row[1]
            else:
                receipt = str(uuid4())
                db.execute("INSERT INTO effects VALUES (?, ?, ?, ?)", (tenant_id, action_id, digest, receipt))
        if fail_after_commit:
            raise RuntimeError("injected lost reply after commit")
        return receipt
