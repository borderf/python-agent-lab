"""A runnable DocPilot teaching slice. Start with init, seed, then the API."""

import argparse
from contextlib import asynccontextmanager
from datetime import date
import hmac
import json
import logging
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from practice.enterprise_ai.docpilot_question import validate_answer
from practice.enterprise_ai.retrieval_baseline import DATA, bigrams, eligible_sources, rank_sources
from .database import AnswerRecord, Document, Feedback, database_url, make_engine, migrate
from .models import configured_model
from .files import extract_pages

DEFAULT_DB = Path(".learning-labs/docpilot.sqlite")
logger = logging.getLogger("docpilot")


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    section: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=40)
    valid_from: date
    valid_to: date | None = None
    text: str = Field(min_length=1, max_length=40000)

    @model_validator(mode="after")
    def check_dates(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must follow valid_from")
        return self


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=1000)
    as_of: date


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    answer_id: str = Field(min_length=1, max_length=40)
    helpful: bool
    note: str = Field(default="", max_length=1000)


def document_dict(row: Document) -> dict:
    return {column.name: getattr(row, column.name) for column in Document.__table__.columns}


def put_document(session: Session, tenant: str, body: DocumentInput) -> bool:
    values = body.model_dump(mode="json")
    old = session.get(Document, (tenant, body.source_id))
    if old:
        if document_dict(old) != {"tenant_id": tenant, **values}:
            raise ValueError("Source ID already exists with different content; create a new version ID")
        return False
    session.add(Document(tenant_id=tenant, **values))
    session.flush()
    return True


def seed(url: str) -> None:
    engine = make_engine(url)
    try:
        with Session(engine) as session, session.begin():
            for row in json.loads((DATA / "policies.json").read_text(encoding="utf-8")):
                if not row.get("trusted_policy", True):
                    continue
                fields = {name: row[name] for name in DocumentInput.model_fields}
                put_document(session, row["tenant_id"], DocumentInput(**fields))
    finally:
        engine.dispose()


def create_app(url: str | None = None, model=None, tokens: dict | None = None) -> FastAPI:
    url = url or database_url(DEFAULT_DB)
    model = model or configured_model()
    if tokens is None:
        first, second = os.getenv("LAB_TOKEN_A", "demo-a"), os.getenv("LAB_TOKEN_B", "demo-b")
        if not first or not second or first == second:
            raise ValueError("LAB_TOKEN_A and LAB_TOKEN_B must be nonempty and distinct")
        tokens = {first: "tenant-a", second: "tenant-b"}

    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(url)
        try:
            if not {"documents", "answers", "feedback"} <= set(inspect(engine).get_table_names()):
                raise RuntimeError("Run python -m practice.integration_labs.docpilot init first")
            app.state.engine = engine
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="DocPilot 教学参考切片", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if credentials:
            for token, tenant in tokens.items():
                if hmac.compare_digest(token.encode(), credentials.credentials.encode()):
                    return tenant
        raise HTTPException(401, "需要有效的教学身份", headers={"WWW-Authenticate": "Bearer"})

    def session():
        with Session(app.state.engine) as value:
            yield value

    @app.middleware("http")
    async def request_log(request, call_next):
        request_id = str(uuid4())
        start = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("request=%s method=%s status=%s elapsed_ms=%.1f", request_id,
                    request.method, response.status_code, (perf_counter() - start) * 1000)
        return response

    @app.get("/")
    def page():
        return FileResponse(Path(__file__).with_name("docpilot.html"))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/documents")
    def upload(body: DocumentInput, tenant: str = Depends(identity), db: Session = Depends(session)):
        try:
            with db.begin():
                created = put_document(db, tenant, body)
        except (ValueError, IntegrityError) as error:
            raise HTTPException(409, "来源冲突，请核对或使用新版本 ID") from error
        return {"document_id": body.source_id, "created": created, "status": "ready"}

    @app.get("/api/documents/{source_id}")
    def source(source_id: str, tenant: str = Depends(identity), db: Session = Depends(session)):
        row = db.get(Document, (tenant, source_id))
        if row is None:
            raise HTTPException(404, "未找到可访问来源")
        return document_dict(row)

    def retrieve(db, tenant, body):
        rows = [document_dict(row) for row in db.scalars(select(Document).where(Document.tenant_id == tenant))]
        visible = eligible_sources(rows, tenant, body.as_of.isoformat())
        # This baseline uses literal overlap. Semantic retrieval is the next lab.
        terms = bigrams(body.question)
        visible = [row for row in visible if terms & bigrams(row["text"] + row["title"] + row["section"])]
        by_id = {row["source_id"]: row for row in visible}
        return [by_id[key] for key in rank_sources(body.question, visible, "bigram")[:3]]

    @app.post("/api/search")
    def search(body: QuestionInput, tenant: str = Depends(identity), db: Session = Depends(session)):
        return {"items": retrieve(db, tenant, body)}

    @app.post("/api/questions")
    def question(body: QuestionInput, tenant: str = Depends(identity), db: Session = Depends(session)):
        evidence = retrieve(db, tenant, body)
        db.rollback()  # Release the read transaction before waiting for a model.
        if evidence:
            try:
                generated = model.answer(body.question, evidence)
                result = validate_answer(generated.content, {row["source_id"]: row["text"] for row in evidence})
            except (ValueError, RuntimeError) as error:
                raise HTTPException(502, "模型响应失败或引用无效") from error
            result.update(model=generated.model, usage=generated.usage)
        else:
            result = {"answer": "当前可访问资料中没有找到依据，请补充材料。", "citations": [],
                      "needs_review": True, "model": "none", "usage": {}}
        by_id = {row["source_id"]: row for row in evidence}
        for citation in result["citations"]:
            row = by_id[citation["source_id"]]
            citation.update(version=row["version"], section=row["section"])
        answer_id = str(uuid4())
        result.update(answer_id=answer_id, as_of=str(body.as_of), candidates=list(by_id))
        with db.begin():
            db.add(AnswerRecord(id=answer_id, tenant_id=tenant, payload=result))
        return result

    @app.post("/api/feedback", status_code=201)
    def feedback(body: FeedbackInput, tenant: str = Depends(identity), db: Session = Depends(session)):
        answer = db.get(AnswerRecord, body.answer_id)
        if answer is None or answer.tenant_id != tenant:
            raise HTTPException(404, "未找到可访问的回答")
        key = str(uuid4())
        db.add(Feedback(id=key, tenant_id=tenant, **body.model_dump()))
        db.commit()
        return {"feedback_id": key}

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "seed", "import-file"))
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--source-prefix", default="manual")
    parser.add_argument("--tenant", default="tenant-a", help="trusted local import identity")
    parser.add_argument("--valid-from", type=date.fromisoformat, default=date(2026, 7, 1))
    args = parser.parse_args()
    url = database_url(args.db)
    if args.action == "init":
        migrate(url)
    elif args.action == "seed":
        seed(url)
    else:
        if args.file is None:
            parser.error("import-file requires --file")
        pages = extract_pages(args.file)
        documents = [DocumentInput(source_id=f"{args.source_prefix}-p{index}", title=args.file.name,
                                   section=section, version="1", valid_from=args.valid_from, text=text)
                     for index, (section, text) in enumerate(pages, 1)]
        engine = make_engine(url)
        try:
            with Session(engine) as session, session.begin():
                for document in documents:
                    put_document(session, args.tenant, document)
        finally:
            engine.dispose()
    print(f"{args.action}: {args.db}")


if __name__ == "__main__":
    main()
