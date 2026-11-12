"""Six cumulative persistence steps; the supplied module is the learner's adapter."""
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from practice.learning_projects import docpilot_reference as core


def document(**changes):
    return {"source_id": "policy", "tenant_id": "a", "version": "1", "title": "付款制度",
            "text": "预付款不得超过20%。", "valid_from": "2026-01-01", "valid_to": None, **changes}


def query(implementation, db, **changes):
    return implementation.search(db, "预付款", tenant_id=changes.get("tenant_id", "a"),
                                 as_of=changes.get("as_of", "2026-06-01"), core=core)


def test_s01_validate_before_write(implementation, tmp_path):
    db = tmp_path / "sources.db"
    with pytest.raises(ValueError):
        implementation.put_document(db, document(text=" "), core=core)
    assert implementation.put_document(db, document(), core=core) is True


def test_s02_upload_is_immediately_searchable(implementation, tmp_path):
    db = tmp_path / "sources.db"
    assert query(implementation, db) == []
    implementation.put_document(db, document(), core=core)
    assert query(implementation, db)[0]["text"] == document()["text"]
    implementation.put_document(db, document(source_id="second", text="预付款材料必须复核。"), core=core)
    assert len(query(implementation, db)) == 2


def test_s03_duplicate_and_conflict(implementation, tmp_path):
    db = tmp_path / "sources.db"
    implementation.put_document(db, document(), core=core)
    assert implementation.put_document(db, document(), core=core) is False
    with pytest.raises(ValueError):
        implementation.put_document(db, document(text="预付款80%"), core=core)
    assert query(implementation, db)[0]["text"] == document()["text"]


def test_s04_tenant_and_half_open_date(implementation, tmp_path):
    db = tmp_path / "sources.db"
    implementation.put_document(db, document(valid_to="2026-07-01"), core=core)
    implementation.put_document(db, document(tenant_id="b", text="预付款80%"), core=core)
    assert len(query(implementation, db)) == 1
    assert query(implementation, db, as_of="2026-07-01") == []
    assert query(implementation, db, tenant_id="c") == []


def test_s05_new_process_reuses_storage(implementation, tmp_path):
    db = tmp_path / "sources.db"
    implementation.put_document(db, document(), core=core)
    script = ("import importlib,json,sys; from practice.learning_projects import docpilot_reference as c; "
              "m=importlib.import_module(sys.argv[1]); "
              "print(json.dumps(m.search(sys.argv[2], '预付款', tenant_id='a', as_of='2026-06-01', core=c)))")
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script, implementation.__name__, str(db)],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    assert json.loads(result.stdout)[0]["text"] == document()["text"]


def test_s06_injected_core_remains_authority(implementation, tmp_path):
    db = tmp_path / "sources.db"
    calls = []

    def wrapped(name):
        def invoke(*args, **kwargs):
            calls.append(name)
            return getattr(core, name)(*args, **kwargs)
        return invoke

    injected = SimpleNamespace(**{name: wrapped(name) for name in
                                 ("normalize_document", "build_index", "search", "answer")})
    implementation.put_document(db, document(), core=injected)
    implementation.search(db, "预付款", tenant_id="a", as_of="2026-06-01", core=injected)
    with pytest.raises(ValueError):
        implementation.answer(db, "预付款", tenant_id="a", as_of="2026-06-01", core=injected,
                              model=lambda *_: {"answer": "编造", "citations": [], "needs_review": False})
    assert {"normalize_document", "build_index", "search", "answer"} <= set(calls)
