"""Durable approval workflow around the simulated idempotent effect receiver.

tenant_id and approve() are trusted service-side inputs, not authentication.
Once executing, payload edits are forbidden until the effect is reconciled.
"""
from contextlib import closing
import json
import sqlite3

from practice.learning_projects.approval_reference import payload_hash, submit


def _connect(db_path):
    db = sqlite3.connect(db_path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS tasks (tenant_id TEXT, task_id TEXT, version INTEGER NOT NULL, "
               "payload TEXT NOT NULL, payload_hash TEXT NOT NULL, approved_hash TEXT, "
               "status TEXT NOT NULL, receipt TEXT, PRIMARY KEY(tenant_id, task_id))")
    return db


def _scope(tenant_id, task_id):
    if any(not isinstance(value, str) or not value.strip() for value in (tenant_id, task_id)):
        raise ValueError("nonempty tenant and task IDs required")
    return tenant_id, task_id


def _get(db, scope, expected_version=None):
    row = db.execute("SELECT * FROM tasks WHERE tenant_id=? AND task_id=?", scope).fetchone()
    if row is None:
        raise LookupError("task not found")
    if expected_version is not None:
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("positive integer version required")
        if row["version"] != expected_version:
            raise PermissionError("stale task version")
    return dict(row)


def load(db_path, *, tenant_id, task_id):
    with closing(_connect(db_path)) as db:
        row = _get(db, _scope(tenant_id, task_id))
    row["payload"] = json.loads(row["payload"])
    return row


def prepare(db_path, *, tenant_id, task_id, payload):
    scope = _scope(tenant_id, task_id)
    digest = payload_hash(payload)
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    with closing(_connect(db_path)) as db, db:
        try:
            db.execute("INSERT INTO tasks VALUES (?, ?, 1, ?, ?, NULL, 'waiting_approval', NULL)",
                       (*scope, content, digest))
        except sqlite3.IntegrityError as error:
            raise ValueError("task already exists") from error
    return load(db_path, tenant_id=tenant_id, task_id=task_id)


def change_payload(db_path, *, tenant_id, task_id, expected_version, payload):
    scope = _scope(tenant_id, task_id)
    digest = payload_hash(payload)
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    with closing(_connect(db_path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = _get(db, scope, expected_version)
        if row["status"] not in {"waiting_approval", "approved"}:
            raise ValueError("executing or completed payload is frozen")
        db.execute("UPDATE tasks SET version=version+1, payload=?, payload_hash=?, approved_hash=NULL, "
                   "status='waiting_approval' WHERE tenant_id=? AND task_id=?", (content, digest, *scope))
    return load(db_path, tenant_id=tenant_id, task_id=task_id)


def approve(db_path, *, tenant_id, task_id, expected_version, expected_hash):
    scope = _scope(tenant_id, task_id)
    with closing(_connect(db_path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = _get(db, scope, expected_version)
        if row["status"] != "waiting_approval" or row["payload_hash"] != expected_hash:
            raise PermissionError("approval no longer matches the displayed payload")
        db.execute("UPDATE tasks SET approved_hash=payload_hash, status='approved' "
                   "WHERE tenant_id=? AND task_id=?", scope)
    return load(db_path, tenant_id=tenant_id, task_id=task_id)


def resume(db_path, effects_db, *, tenant_id, task_id, expected_version, fail_after_commit=False):
    scope = _scope(tenant_id, task_id)
    with closing(_connect(db_path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = _get(db, scope, expected_version)
        if row["status"] == "completed":
            return row["receipt"]
        if row["status"] not in {"approved", "executing"} or row["approved_hash"] != row["payload_hash"]:
            raise PermissionError("current payload has not been approved")
        db.execute("UPDATE tasks SET status='executing' WHERE tenant_id=? AND task_id=?", scope)
    # This transaction cannot include the remote receiver. Reuse its durable key
    # after a crash; never infer 'no effect' from a missing local receipt.
    action_id = json.dumps([task_id, row["version"]], ensure_ascii=False, separators=(",", ":"))
    receipt = submit(effects_db, tenant_id=tenant_id, action_id=action_id,
                     payload=json.loads(row["payload"]), approved_hash=row["approved_hash"],
                     fail_after_commit=fail_after_commit)
    with closing(_connect(db_path)) as db, db:
        db.execute("UPDATE tasks SET status='completed', receipt=? "
                   "WHERE tenant_id=? AND task_id=? AND version=? AND status='executing'",
                   (receipt, *scope, expected_version))
    return receipt
