"""The HTTP adapter's boundaries, separate from the learner completion score."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from practice.learning_projects import docpilot_reference as core
from practice.learning_projects.service import make_app


DOC = {"source_id": "p", "tenant_id": "a", "version": "1", "title": "付款",
       "text": "预付款20%", "valid_from": "2026-07-01", "valid_to": None}
BODY = {"question": "预付款", "as_of": "2026-07-01"}
AUTH = {"Authorization": "Bearer demo-a"}


def test_http_identity_and_body_scope():
    with TestClient(make_app(core, [DOC, {**DOC, "tenant_id": "b", "text": "预付款秘密"}])) as client:
        assert client.post("/api/search", json=BODY).status_code == 401
        assert client.post("/api/search", json={**BODY, "tenant_id": "b"}, headers=AUTH).status_code == 422
        response = client.post("/api/search", json=BODY, headers=AUTH)
        assert response.status_code == 200
        assert {row["tenant_id"] for row in response.json()["items"]} == {"a"}
        assert "秘密" not in response.text


def test_http_source_and_date_match_core():
    with TestClient(make_app(core, [DOC])) as client:
        before = client.post("/api/questions", json={**BODY, "as_of": "2026-06-30"}, headers=AUTH)
        assert before.json()["citations"] == []
        result = client.post("/api/questions", json=BODY, headers=AUTH)
        assert result.status_code == 200
        assert result.json()["citations"][0]["source_id"] == "p"


def test_http_model_timeout_is_not_no_evidence():
    def timeout(*args):
        raise TimeoutError("injected")
    with TestClient(make_app(core, [DOC], model=timeout)) as client:
        assert client.post("/api/questions", json=BODY, headers=AUTH).status_code == 504


def test_http_bad_citation_is_failure():
    with TestClient(make_app(core, [DOC], model=lambda *args: {})) as client:
        assert client.post("/api/questions", json=BODY, headers=AUTH).status_code == 502


def test_http_invalid_date_never_calls_model():
    def forbidden(*args):
        raise AssertionError("model should not run")
    with TestClient(make_app(core, [DOC], model=forbidden)) as client:
        assert client.post("/api/questions", json={**BODY, "as_of": "2026-02-30"}, headers=AUTH).status_code == 422
