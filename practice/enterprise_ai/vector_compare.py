"""Compare lexical, embedding, rank fusion and optional model reranking on one corpus."""
import argparse
from functools import cache, partial
import json
from math import hypot, isfinite, sumprod

from .ollama_local import assistant_message, decode_json, post
from .retrieval_baseline import DATA, evaluate, rank_sources


def unit_vectors(texts: list[str], model: str) -> list[list[float]]:
    result = post("/api/embed", {"model": model, "input": texts, "truncate": False})
    vectors = result.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError("one embedding per input required")
    normalized = []
    for vector in vectors:
        if not isinstance(vector, list) or not vector or not all(
            type(x) in (int, float) and isfinite(x) for x in vector
        ):
            raise ValueError("invalid embedding")
        norm = hypot(*vector)
        if not norm or not isfinite(norm):
            raise ValueError("invalid embedding norm")
        normalized.append([v / norm for v in vector])
    return normalized


def source_text(row: dict) -> str:
    return "\n".join([row["title"], row["section"], row["text"]])


@cache
def embed_text(model: str, text: str) -> list[float]:
    # Key includes model; the short-lived command uses an immutable fixture corpus.
    return unit_vectors([text], model)[0]


def dense_rank(query: str, sources: list[dict], *, model: str) -> list[str]:
    q = embed_text(model, query)
    scores = []
    for row in sources:
        v = embed_text(model, source_text(row))
        scores.append((-sumprod(q, v), row["source_id"]))
    return [key for _, key in sorted(scores)]


def fuse(left: list[str], right: list[str]) -> list[str]:
    scores = {}
    for ranking in (left, right):
        for rank, key in enumerate(dict.fromkeys(ranking), 1):
            scores[key] = scores.get(key, 0.0) + 1 / (60 + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


def rerank(query: str, ranking: list[str], sources: list[dict], model: str) -> list[str]:
    shortlist = ranking[:6]
    texts = {row["source_id"]: source_text(row) for row in sources}
    candidates = {key: texts[key] for key in shortlist}
    messages = [
        {"role": "system", "content": "按与问题的相关性重排候选。输出 JSON 对象 ids，含全部候选ID各一次。"},
        {"role": "user", "content": json.dumps({"query": query, "candidates": candidates}, ensure_ascii=False)},
    ]
    response = post("/api/chat", {"model": model, "stream": False, "format": "json",
                                  "messages": messages, "options": {"temperature": 0}})
    content = assistant_message(response).get("content")
    result = decode_json(content) if isinstance(content, str) else None
    ids = result.get("ids") if isinstance(result, dict) else None
    if (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)
            or sorted(ids) != sorted(shortlist)):
        raise ValueError("reranker must return a permutation of its candidates")
    return ids + ranking[len(shortlist):]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embed-model", required=True)
    parser.add_argument("--rerank-model", help="optional local chat model for listwise reranking")
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    args = parser.parse_args()
    if not args.embed_model.strip():
        parser.error("--embed-model must not be empty")
    if args.rerank_model is not None and not args.rerank_model.strip():
        parser.error("--rerank-model must not be empty when provided")
    policies = json.loads((DATA / "policies.json").read_text(encoding="utf-8"))
    cases = json.loads((DATA / "retrieval_cases.json").read_text(encoding="utf-8"))
    cases = [case for case in cases if case.get("split", "dev") == args.split]

    dense = partial(dense_rank, model=args.embed_model)

    def hybrid(query, sources):
        return fuse(rank_sources(query, sources, "bigram"), dense(query, sources))

    print(f"split={args.split} embedding={args.embed_model} reranker={args.rerank_model}")
    evaluate(policies, cases, "bigram")
    evaluate(policies, cases, "dense", dense)
    evaluate(policies, cases, "rrf", hybrid)
    if args.rerank_model:
        def reranked(query, sources):
            return rerank(query, hybrid(query, sources), sources, args.rerank_model)
        evaluate(policies, cases, "rrf+rerank", reranked)


if __name__ == "__main__":
    main()
