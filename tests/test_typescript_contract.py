"""The frozen wire examples consumed by TS must match real Python HTTP output."""
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from practice.learning_projects import docpilot_reference as core
from practice.learning_projects.service import make_app
from practice.integration_labs.database import database_url, migrate
from practice.integration_labs.docpilot import create_app
from practice.integration_labs.models import FixtureModel

FIXTURES = Path(__file__).resolve().parents[1] / "typescript-examples/tests/fixtures"
BODY = {"question": "预付款", "as_of": "2026-01-01"}


def fixture(name):
    return json.loads((FIXTURES / f"search-{name}.json").read_text(encoding="utf-8"))


def test_core_http_wire_matches_typescript_fixture():
    expected = fixture("core")
    document = {key: value for key, value in expected["items"][0].items()
                if key not in {"start", "end", "chunk_id"}}
    with TestClient(make_app(core, [document])) as client:
        response = client.post("/api/search", json=BODY, headers={"Authorization": "Bearer demo-a"})
        assert response.status_code == 200
        assert response.json() == expected
        text = response.json()["items"][0]["text"]
        assert len(text) == 11  # emoji is one Python code point, two JS UTF-16 code units.


def test_persistent_http_wire_matches_typescript_fixture(tmp_path):
    expected = fixture("persistent")
    document = dict(expected["items"][0])
    document.pop("tenant_id")
    url = database_url(tmp_path / "wire.sqlite")
    migrate(url)
    with TestClient(create_app(url, model=FixtureModel(), tokens={"demo-a": "tenant-a"})) as client:
        auth = {"Authorization": "Bearer demo-a"}
        assert client.post("/api/documents", json=document, headers=auth).status_code == 200
        response = client.post("/api/search", json=BODY, headers=auth)
        assert response.status_code == 200
        assert response.json() == expected
