"""HTTP wiring keeps the learner core and persistence adapter on the real path."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from practice.learning_projects import docpilot_reference as core
from practice.learning_projects import persistence_reference as persistence
from practice.learning_projects.service import make_app


def test_upload_search_restart_and_tenant(tmp_path):
    db = tmp_path / "sources.db"
    app = make_app(core, [], persistence=persistence, db_path=db)
    a, b = {"Authorization": "Bearer demo-a"}, {"Authorization": "Bearer demo-b"}
    document = {"source_id": "p", "version": "1", "title": "付款制度", "text": "预付款20%",
                "valid_from": "2026-01-01", "valid_to": None}
    query = {"question": "预付款", "as_of": "2026-06-01"}
    with TestClient(app) as client:
        assert client.post("/api/sources", json=document).status_code == 401
        assert client.post("/api/sources", headers=a, json={**document, "tenant_id": "b"}).status_code == 422
        assert client.post("/api/sources", headers=a, json=document).json()["created"] is True
        assert client.post("/api/sources", headers=a, json=document).json()["created"] is False
        assert client.post("/api/sources", headers=a, json={**document, "text": "预付款80%"}).status_code == 409
        assert client.post("/api/sources", headers=a, json={**document, "valid_to": "2025-01-01"}).status_code == 422
        assert client.post("/api/search", headers=b, json=query).json() == {"items": []}
        assert client.post("/api/questions", headers=a, json=query).json()["citations"][0]["quote"] == "预付款20%"
    with TestClient(make_app(core, [], persistence=persistence, db_path=db)) as client:
        assert client.post("/api/search", headers=a, json=query).json()["items"][0]["text"] == "预付款20%"
