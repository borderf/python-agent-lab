"""Project-level regressions for the staged reference implementation."""

import io
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from practice.integration_labs.database import Document, database_url, make_engine, migrate
from practice.integration_labs.docpilot import create_app, seed
from practice.integration_labs.models import FixtureModel, ModelAnswer


@pytest.fixture
def url(tmp_path):
    value = database_url(tmp_path / "course.sqlite")
    migrate(value)
    seed(value)
    return value


HEADERS = {"Authorization": "Bearer demo-a"}


def test_docpilot_real_http_database_citations_and_feedback(url):
    with TestClient(create_app(url)) as client:
        result = client.post("/api/questions", headers=HEADERS, json={
            "question": "本租户预付款比例上限是多少？", "as_of": "2026-10-01"})
        assert result.status_code == 200
        assert result.headers["x-request-id"]
        answer = result.json()
        assert answer["model"] == "fixture" and "20%" in answer["answer"]
        assert "policy-a-old" not in answer["candidates"]
        assert "policy-b-current" not in answer["candidates"]
        source = client.get("/api/documents/" + answer["citations"][0]["source_id"], headers=HEADERS)
        assert source.status_code == 200
        assert answer["citations"][0]["quote"] in source.json()["text"]
        assert client.post("/api/feedback", headers=HEADERS, json={
            "answer_id": answer["answer_id"], "helpful": False, "note": "需要解释适用条件"}).status_code == 201
        assert client.post("/api/feedback", headers={"Authorization": "Bearer demo-b"}, json={
            "answer_id": answer["answer_id"], "helpful": True}).status_code == 404


def test_docpilot_history_auth_bad_identity_and_unanswered(url):
    with TestClient(create_app(url)) as client:
        body = {"question": "预付款比例上限？", "as_of": "2026-06-30"}
        assert client.post("/api/questions", json=body).status_code == 401
        assert client.post("/api/questions", headers=HEADERS, json={**body, "tenant_id": "tenant-b"}).status_code == 422
        result = client.post("/api/questions", headers=HEADERS, json=body).json()
        assert "30%" in result["answer"] and "policy-a-current" not in result["candidates"]
        assert client.get("/api/documents/policy-b-current", headers=HEADERS).status_code == 404
        assert client.post("/api/questions", headers=HEADERS, json={
            "question": "火星天气", "as_of": "2026-10-01"}).json()["citations"] == []


def test_document_replay_conflict_and_process_restart(url):
    body = {"source_id": "manual-v1", "title": "交接规则", "section": "正文", "version": "1",
            "valid_from": "2026-01-01", "text": "保留交接单编号。"}
    with TestClient(create_app(url)) as client:
        assert client.post("/api/documents", headers=HEADERS, json=body).json()["created"]
        assert not client.post("/api/documents", headers=HEADERS, json=body).json()["created"]
        assert client.post("/api/documents", headers=HEADERS, json={**body, "text": "冲突内容"}).status_code == 409
        assert client.post("/api/documents", headers=HEADERS, json={**body, "valid_to": "2025-01-01"}).status_code == 422
    with TestClient(create_app(url)) as reopened:
        assert reopened.get("/api/documents/manual-v1", headers=HEADERS).json()["text"] == body["text"]


def test_bad_citation_is_a_model_failure_not_a_persisted_answer(url):
    class BadModel(FixtureModel):
        def answer(self, question, evidence):
            payload = {"answer": "20%", "citations": [{"source_id": "invented", "quote": "20%"}], "needs_review": False}
            return ModelAnswer(json.dumps(payload), "bad-fixture", {})
    with TestClient(create_app(url, model=BadModel())) as client:
        assert client.post("/api/questions", headers=HEADERS, json={
            "question": "预付款比例", "as_of": "2026-10-01"}).status_code == 502


def test_real_migration_preserves_revision_001_data(tmp_path):
    url = database_url(tmp_path / "migration.sqlite")
    migrate(url, "001")
    seed(url)
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            before = list(session.scalars(select(Document.source_id)))
        migrate(url)
        with Session(engine) as session:
            assert list(session.scalars(select(Document.source_id))) == before
    finally:
        engine.dispose()


def test_pdf_page_text_keeps_its_location_and_blank_pages_fail(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    from practice.integration_labs.files import extract_pages

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    content = DecodedStreamObject()
    content.set_data(b'BT /F1 12 Tf 20 100 Td (Payment limit is 20 percent.) Tj ET')
    page.replace_contents(content)
    pdf = tmp_path / 'policy.pdf'
    writer.write(pdf)
    assert extract_pages(pdf) == [('PDF 第 1 页', 'Payment limit is 20 percent.')]
    writer.add_blank_page(width=300, height=200)
    writer.write(pdf)
    with pytest.raises(ValueError, match='PDF 第 2 页'):
        extract_pages(pdf)


@pytest.mark.parametrize('choices', [[], [None], [{'finish_reason': 'length'}],
                                     [{'finish_reason': 'stop', 'message': None}]])
def test_hosted_adapter_rejects_incomplete_or_malformed_responses(monkeypatch, choices):
    from practice.integration_labs import models
    monkeypatch.setattr(models, 'urlopen', lambda request, timeout: io.BytesIO(json.dumps({'choices': choices}).encode()))
    model = models.HttpModel('hosted', 'fixture', 'https://provider.example/chat/completions', 'fixture-key')
    with pytest.raises(ValueError):
        model.answer('question', [])


def test_hosted_adapter_preserves_internal_contract_and_usage(monkeypatch):
    from practice.integration_labs import models
    def response(request, timeout):
        assert request.headers['Authorization'] == 'Bearer fixture-key'
        assert json.loads(request.data)['stream'] is False
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
                                      'usage': {'prompt_tokens': 12, 'completion_tokens': 3}}).encode())
    monkeypatch.setattr(models, 'urlopen', response)
    result = models.HttpModel('hosted', 'fixture', 'https://provider.example/chat/completions', 'fixture-key').answer('question', [])
    assert result.content == '{}' and result.usage['completion_tokens'] == 3

