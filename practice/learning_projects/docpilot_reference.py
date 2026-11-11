"""Offline teaching baseline, not a semantic answer verifier or production RAG.

Offsets refer to Unicode code points in the normalized text. Dates are ISO
dates with a half-open validity interval. The supplied model is a callback.
"""

from copy import deepcopy
from datetime import date
import json


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()


def _date(value):
    if not isinstance(value, str):
        raise ValueError("date must be ISO text")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return value


def normalize_document(raw):
    fields = {"source_id", "tenant_id", "version", "title", "text", "valid_from", "valid_to"}
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ValueError("unexpected document fields")
    result = {key: _text(raw[key], key) for key in fields - {"valid_from", "valid_to"}}
    result["valid_from"] = _date(raw["valid_from"])
    result["valid_to"] = None if raw["valid_to"] is None else _date(raw["valid_to"])
    if result["valid_to"] is not None and result["valid_to"] <= result["valid_from"]:
        raise ValueError("invalid validity interval")
    return result


def build_index(documents, chunk_chars=120):
    if type(chunk_chars) is not int or chunk_chars < 1:
        raise ValueError("chunk_chars must be a positive integer")
    sources = {}
    for raw in documents:
        document = normalize_document(raw)
        key = (document["tenant_id"], document["source_id"], document["version"])
        if key in sources and sources[key] != document:
            raise ValueError("same source version has different content")
        sources[key] = document
    chunks = []
    for key, document in sorted(sources.items()):
        for start in range(0, len(document["text"]), chunk_chars):
            end = min(start + chunk_chars, len(document["text"]))
            # JSON encoding avoids collisions caused by delimiters inside IDs.
            chunk_id = json.dumps([*key, start], ensure_ascii=False, separators=(",", ":"))
            chunks.append({**document, "text": document["text"][start:end],
                           "start": start, "end": end, "chunk_id": chunk_id})
    return chunks


def _terms(text):
    normalized = "".join(text.lower().split())
    return {normalized[i:i + 2] for i in range(len(normalized) - 1)}


def search(index, question, *, tenant_id, as_of, limit=3):
    question = _text(question, "question")
    tenant_id = _text(tenant_id, "tenant_id")
    as_of = _date(as_of)
    if len(question) < 2 or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("question too short or limit outside 1..10")
    query_terms = _terms(question)
    scored = []
    for chunk in index:
        if chunk["tenant_id"] != tenant_id:
            continue
        if chunk["valid_from"] > as_of or (chunk["valid_to"] is not None and as_of >= chunk["valid_to"]):
            continue
        score = len(query_terms & _terms(chunk["title"] + chunk["text"]))
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda row: (-row[0], row[1]["source_id"], row[1]["version"], row[1]["start"]))
    return [deepcopy(chunk) for _, chunk in scored[:limit]]


def answer(index, question, *, tenant_id, as_of, model):
    evidence = search(index, question, tenant_id=tenant_id, as_of=as_of)
    if not evidence:
        return {"answer": "当前可访问资料中没有找到依据。", "citations": [], "needs_review": True}
    # Keep the trusted evidence independent of a callback's mutable arguments.
    generated = model(question, deepcopy(evidence))
    if not isinstance(generated, dict) or set(generated) != {"answer", "citations", "needs_review"}:
        raise ValueError("unexpected answer fields")
    text = _text(generated["answer"], "answer")
    if type(generated["needs_review"]) is not bool or not isinstance(generated["citations"], list):
        raise ValueError("invalid review flag or citations")
    by_id = {chunk["chunk_id"]: chunk for chunk in evidence}
    citations, seen = [], set()
    for citation in generated["citations"]:
        if not isinstance(citation, dict) or set(citation) != {"chunk_id", "quote"}:
            raise ValueError("unexpected citation fields")
        chunk_id, quote = citation["chunk_id"], citation["quote"]
        if not isinstance(chunk_id, str) or chunk_id not in by_id:
            raise ValueError("citation outside evidence")
        if not isinstance(quote, str) or not quote.strip() or quote not in by_id[chunk_id]["text"]:
            raise ValueError("quote absent from source")
        if (chunk_id, quote) in seen:
            raise ValueError("duplicate citation")
        seen.add((chunk_id, quote))
        chunk = by_id[chunk_id]
        citations.append({**citation, "source_id": chunk["source_id"], "version": chunk["version"],
                          "start": chunk["start"], "end": chunk["end"]})
    if not citations and not generated["needs_review"]:
        raise ValueError("uncited answer must require review")
    return {"answer": text, "citations": citations, "needs_review": generated["needs_review"]}
