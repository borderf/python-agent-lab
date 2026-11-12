"""Six learner workflow contracts; receiver is a real local SQLite simulation."""
import json
import sqlite3
import subprocess
import sys

import pytest


def scope(**changes):
    return {"tenant_id": "a", "task_id": "purchase-1", **changes}


def ready(implementation, db):
    row = implementation.prepare(db, **scope(), payload={"amount_cents": 2000})
    return implementation.approve(db, **scope(), expected_version=1, expected_hash=row["payload_hash"])


def test_s01_save_and_load(implementation, tmp_path):
    db = tmp_path / "tasks.db"
    payload = {"amount_cents": 2000}
    row = implementation.prepare(db, **scope(), payload=payload)
    payload["amount_cents"] = 1
    saved = implementation.load(db, **scope())
    assert saved["payload"] == {"amount_cents": 2000}
    assert saved["version"] == 1 and saved["status"] == "waiting_approval"
    assert saved["payload_hash"] == row["payload_hash"] and saved["receipt"] is None


def test_s02_scope_and_unapproved_resume(implementation, tmp_path):
    db, effects = tmp_path / "tasks.db", tmp_path / "effects.db"
    implementation.prepare(db, **scope(), payload={"amount_cents": 2000})
    with pytest.raises(LookupError):
        implementation.load(db, **scope(tenant_id="b"))
    with pytest.raises(PermissionError):
        implementation.resume(db, effects, **scope(), expected_version=1)


def test_s03_change_invalidates_approval(implementation, tmp_path):
    db, effects = tmp_path / "tasks.db", tmp_path / "effects.db"
    old = ready(implementation, db)
    new = implementation.change_payload(db, **scope(), expected_version=1, payload={"amount_cents": 9000})
    assert new["version"] == 2 and new["approved_hash"] is None and new["status"] == "waiting_approval"
    with pytest.raises(PermissionError):
        implementation.approve(db, **scope(), expected_version=2, expected_hash=old["payload_hash"])
    with pytest.raises(PermissionError):
        implementation.resume(db, effects, **scope(), expected_version=1)
    with pytest.raises(PermissionError):
        implementation.resume(db, effects, **scope(), expected_version=2)


def test_s04_replay_has_one_effect(implementation, tmp_path):
    db, effects = tmp_path / "tasks.db", tmp_path / "effects.db"
    ready(implementation, db)
    receipt = implementation.resume(db, effects, **scope(), expected_version=1)
    assert isinstance(receipt, str) and receipt
    assert implementation.resume(db, effects, **scope(), expected_version=1) == receipt
    assert implementation.load(db, **scope())["status"] == "completed"
    with sqlite3.connect(effects) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == 1


def test_s05_lost_reply_freezes_payload(implementation, tmp_path):
    db, effects = tmp_path / "tasks.db", tmp_path / "effects.db"
    ready(implementation, db)
    with pytest.raises(RuntimeError, match="after commit"):
        implementation.resume(db, effects, **scope(), expected_version=1, fail_after_commit=True)
    assert implementation.load(db, **scope())["status"] == "executing"
    with pytest.raises(ValueError):
        implementation.change_payload(db, **scope(), expected_version=1, payload={"amount_cents": 9000})
    receipt = implementation.resume(db, effects, **scope(), expected_version=1)
    with sqlite3.connect(effects) as connection:
        assert connection.execute("SELECT receipt FROM effects").fetchall() == [(receipt,)]


def test_s06_new_process_reconciles(implementation, tmp_path):
    db, effects = tmp_path / "tasks.db", tmp_path / "effects.db"
    ready(implementation, db)
    with pytest.raises(RuntimeError, match="after commit"):
        implementation.resume(db, effects, **scope(), expected_version=1, fail_after_commit=True)
    script = ("import importlib,json,sys; m=importlib.import_module(sys.argv[1]); "
              "print(json.dumps(m.resume(sys.argv[2], sys.argv[3], tenant_id='a', "
              "task_id='purchase-1', expected_version=1)))")
    completed = subprocess.run([sys.executable, "-X", "utf8", "-c", script, implementation.__name__,
                                str(db), str(effects)], check=True, capture_output=True,
                               text=True, encoding="utf-8")
    receipt = json.loads(completed.stdout)
    assert implementation.load(db, **scope())["receipt"] == receipt
    with sqlite3.connect(effects) as connection:
        assert connection.execute("SELECT receipt FROM effects").fetchall() == [(receipt,)]
