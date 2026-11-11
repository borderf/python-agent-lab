"""Score a learner's retrieval and export every case, including failures.

This runner measures source recall/rank and program outcomes. It does NOT
automatically grade semantic support or prove real model quality.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
from time import perf_counter


def fixture_quote(question, evidence):
    return {"answer": evidence[0]["text"], "citations": [
        {"chunk_id": evidence[0]["chunk_id"], "quote": evidence[0]["text"]}], "needs_review": True}


def evaluate(core, documents, cases, model=fixture_quote, model_id="fixture-quote"):
    index = core.build_index(documents)
    corpus_hash = hashlib.sha256(json.dumps(documents, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    records = []
    for case in cases:
        started = perf_counter()
        record = {"case_id": case["case_id"], "split": case["split"], "corpus_sha256": corpus_hash,
                  "implementation": core.__name__, "model_id": model_id, "error": None,
                  "recall_at_3": None, "reciprocal_rank": None, "candidate_source_ids": []}
        try:
            arguments = {"tenant_id": case["tenant_id"], "as_of": case["as_of"]}
            chunks = core.search(index, case["question"], **arguments, limit=3)
            ids = list(dict.fromkeys(chunk["source_id"] for chunk in chunks))
            record["candidate_source_ids"] = ids
            expected = set(case["expected_source_ids"])
            if expected:
                record["recall_at_3"] = len(expected & set(ids)) / len(expected)
                record["reciprocal_rank"] = next((1 / rank for rank, key in enumerate(ids, 1) if key in expected), 0)
            record["unexpected_candidate"] = bool(set(ids) - expected)
            result = core.answer(index, case["question"], **arguments, model=model)
            record.update(answer=result["answer"], citations=result["citations"], needs_review=result["needs_review"])
        except Exception as error:
            # Errors are explicit failed records, never silently removed from totals.
            record["error"] = type(error).__name__
        record["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", required=True, help="Your importable RAG core module")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("evaluation_cases.json"))
    parser.add_argument("--split", choices=("development", "holdout", "all"), default="development")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-module", help="Optional module exposing answer(question, evidence)")
    parser.add_argument("--model-id", help="Required actual model/version label when using an adapter")
    args = parser.parse_args()
    if args.model_module and not args.model_id:
        parser.error("--model-module requires --model-id; no silent fixture fallback")
    if args.model_id and not args.model_module:
        parser.error("--model-id requires --model-module; fixture must keep its fixture label")
    core = importlib.import_module(args.implementation)
    model = importlib.import_module(args.model_module).answer if args.model_module else fixture_quote
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = [case for case in dataset["cases"] if args.split == "all" or case["split"] == args.split]
    if not cases:
        parser.error("selected split contains no cases")
    records = evaluate(core, dataset["documents"], cases, model, args.model_id or "fixture-quote")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    answerable = [row for row, case in zip(records, cases) if case["expected_source_ids"]]
    summary = {"cases": len(records), "errors": sum(row["error"] is not None for row in records),
               "answerable_cases": len(answerable), "model_id": args.model_id or "fixture-quote",
               "recall_at_3": sum(row["recall_at_3"] or 0 for row in answerable) / len(answerable) if answerable else None,
               "mrr": sum(row["reciprocal_rank"] or 0 for row in answerable) / len(answerable) if answerable else None,
               "output": str(args.output), "semantic_support": "not_automatically_scored"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
