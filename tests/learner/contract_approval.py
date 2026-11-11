"""Contract for the learner's durable simulated write receiver."""
from contextlib import closing
import sqlite3

import pytest


def send(module, path, **overrides):
    payload = overrides.pop("payload", {"report": "R1", "version": 1})
    return module.submit(path, **{"tenant_id": "a", "action_id": "A1", "payload": payload,
                                 "approved_hash": module.payload_hash(payload), **overrides})


def count(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT count(*) FROM effects").fetchone()[0]


def test_approval_hash_is_canonical(implementation):
    assert implementation.payload_hash({"a": 1, "b": 2}) == implementation.payload_hash({"b": 2, "a": 1})
    assert implementation.payload_hash({"a": 1}) != implementation.payload_hash({"a": 2})


def test_approval_required_before_effect(implementation, tmp_path):
    path = tmp_path / "effects.sqlite"
    with pytest.raises(PermissionError):
        send(implementation, path, approved_hash="wrong")
    if path.exists():
        with closing(sqlite3.connect(path)) as db:
            table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='effects'").fetchone()
            if table:
                assert db.execute("SELECT count(*) FROM effects").fetchone()[0] == 0
    send(implementation, path)
    assert count(path) == 1


def test_replay_returns_same_receipt(implementation, tmp_path):
    path = tmp_path / "effects.sqlite"
    first = send(implementation, path)
    assert isinstance(first, str) and first
    assert send(implementation, path) == first and count(path) == 1


def test_changed_payload_conflicts(implementation, tmp_path):
    path = tmp_path / "effects.sqlite"
    send(implementation, path)
    with pytest.raises(ValueError):
        send(implementation, path, payload={"report": "R1", "version": 2})
    assert count(path) == 1


def test_tenant_scopes_the_key(implementation, tmp_path):
    path = tmp_path / "effects.sqlite"
    a = send(implementation, path)
    b = send(implementation, path, tenant_id="b")
    assert a != b and count(path) == 2


def test_lost_reply_then_recovery(implementation, tmp_path):
    path = tmp_path / "effects.sqlite"
    with pytest.raises(RuntimeError, match="after commit"):
        send(implementation, path, fail_after_commit=True)
    assert count(path) == 1
    receipt = send(implementation, path)
    assert send(implementation, path) == receipt and count(path) == 1


def test_reopen_from_another_process(implementation, tmp_path):
    import subprocess
    import sys
    path = tmp_path / "effects.sqlite"
    receipt = send(implementation, path)
    code = ("import importlib,sys; m=importlib.import_module(sys.argv[1]); "
            "p={'report':'R1','version':1}; print(m.submit(sys.argv[2],tenant_id='a',action_id='A1',"
            "payload=p,approved_hash=m.payload_hash(p)))")
    result = subprocess.run([sys.executable, "-c", code, implementation.__name__, str(path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == receipt and count(path) == 1


def test_invalid_key_is_rejected(implementation, tmp_path):
    with pytest.raises(ValueError):
        send(implementation, tmp_path / "effects.sqlite", action_id="")
