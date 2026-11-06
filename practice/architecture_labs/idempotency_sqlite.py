"""Local transaction/idempotency lesson; not an external exactly-once protocol."""

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import uuid4


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS actions (
            scope TEXT NOT NULL,
            request_key TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            result_id TEXT NOT NULL,
            PRIMARY KEY (scope, request_key)
        );
        CREATE TABLE IF NOT EXISTS effects (
            result_id TEXT PRIMARY KEY,
            content TEXT NOT NULL
        );
    """)
    return db


def apply_local(
    db: sqlite3.Connection,
    scope: str,
    key: str,
    payload: dict,
    *,
    fail_before_commit: bool = False,
) -> str:
    """Scope must come from trusted authorization in a real service."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = sha256(encoded.encode("utf-8")).hexdigest()
    with db:
        # SQLite-specific serialization; this is not a PostgreSQL lock lesson.
        db.execute("BEGIN IMMEDIATE")
        old = db.execute(
            "SELECT payload_hash, result_id FROM actions "
            "WHERE scope = ? AND request_key = ?", (scope, key)
        ).fetchone()
        if old:
            if old[0] != digest:
                raise ValueError("same key, different payload")
            return old[1]
        result_id = str(uuid4())
        db.execute("INSERT INTO actions VALUES (?, ?, ?, ?)",
                   (scope, key, digest, result_id))
        db.execute("INSERT INTO effects VALUES (?, ?)", (result_id, encoded))
        if fail_before_commit:
            raise RuntimeError("injected failure before local commit")
        return result_id


def main() -> None:
    # Keep the self-owned temporary directory inside the known writable lab.
    lab_directory = Path(__file__).resolve().parent
    with TemporaryDirectory(prefix=".architecture-lesson-", dir=lab_directory) as folder:
        path = Path(folder) / "lesson.sqlite"
        db = connect(path)
        try:
            first = apply_local(db, "tenant-a:submit", "k1", {"version": 1})
            assert apply_local(db, "tenant-a:submit", "k1", {"version": 1}) == first
            try:
                apply_local(db, "tenant-a:submit", "k1", {"version": 2})
            except ValueError:
                pass
            else:
                raise AssertionError("changed payload must conflict")
            try:
                apply_local(db, "tenant-a:submit", "k2", {}, fail_before_commit=True)
            except RuntimeError:
                pass
            else:
                raise AssertionError("failure injection did not execute")
            assert db.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == 1
            apply_local(db, "tenant-a:submit", "k2", {})
            apply_local(db, "tenant-b:submit", "k1", {"version": 1})
        finally:
            db.close()
        db = connect(path)
        try:
            assert apply_local(db, "tenant-a:submit", "k1", {"version": 1}) == first
            assert db.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == 3
        finally:
            db.close()
    print("PASS: local replay, payload conflict, scope, rollback, reopen")
    print("Not covered: external side effects, multi-node concurrency, PostgreSQL")


if __name__ == "__main__":
    main()
