"""Put a learner's RAG core behind a small local HTTP boundary.

Run with the web dependency group. This in-memory slice deliberately has no
real login, persistent storage, uploads, streaming, or production deployment.
"""
from datetime import date
import hmac
import importlib
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=1000)
    as_of: date


def fixture_model(question, evidence):
    return {"answer": evidence[0]["text"], "citations": [
        {"chunk_id": evidence[0]["chunk_id"], "quote": evidence[0]["text"]}], "needs_review": True}


def make_app(core, documents, model=fixture_model, tokens=None):
    tokens = dict(tokens if tokens is not None else {"demo-a": "a", "demo-b": "b"})
    if not tokens or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
                         for key, value in tokens.items()):
        raise ValueError("nonempty teaching token mappings required")
    index = core.build_index(documents)
    app = FastAPI(title="累计学习切片：内存索引与教学身份")
    bearer = HTTPBearer(auto_error=False)

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            for token, tenant in tokens.items():
                if hmac.compare_digest(token.encode(), credentials.credentials.encode()):
                    return tenant
        raise HTTPException(401, "需要教学身份", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "fixture", "storage": "memory"}

    @app.post("/api/search")
    def search(body: Query, tenant=Depends(identity)):
        return {"items": core.search(index, body.question, tenant_id=tenant, as_of=body.as_of.isoformat())}

    @app.post("/api/questions")
    def question(body: Query, tenant=Depends(identity)):
        try:
            return core.answer(index, body.question, tenant_id=tenant,
                               as_of=body.as_of.isoformat(), model=model)
        except TimeoutError as error:
            raise HTTPException(504, "模型超时，请稍后重试") from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(502, "模型响应或引用未通过验证") from error

    return app


def create_app():
    core = importlib.import_module(os.getenv("LEARNER_MODULE", "practice.learning_projects.docpilot_reference"))
    base = {"source_id": "policy-a", "tenant_id": "a", "version": "2", "title": "付款制度",
            "text": "预付款比例不得超过20%。", "valid_from": "2026-07-01", "valid_to": None}
    return make_app(core, [base, {**base, "source_id": "policy-old", "version": "1",
        "text": "预付款比例不得超过30%。", "valid_from": "2026-01-01", "valid_to": "2026-07-01"},
        {**base, "tenant_id": "b", "text": "预付款比例不得超过80%。"}])
