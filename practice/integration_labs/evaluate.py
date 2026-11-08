"""Export structural and evidence-coverage checks; semantic grading stays explicit."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient

from .database import database_url, migrate
from .docpilot import create_app, seed

CASES = [
    {"id": "current", "question": "预付款比例上限", "date": "2026-10-01", "token": "demo-a",
     "sources": ["policy-a-current"]},
    {"id": "historical", "question": "预付款比例上限", "date": "2026-06-30", "token": "demo-a",
     "sources": ["policy-a-old"]},
    {"id": "multi_source", "question": "预付款比例上限是多少，供应商缺少资格证明应怎么办？",
     "date": "2026-10-01", "token": "demo-a", "sources": ["policy-a-current", "policy-a-qualification"]},
    {"id": "no_evidence", "question": "火星天气", "date": "2026-10-01", "token": "demo-a", "sources": []},
    {"id": "other_tenant", "question": "预付款比例上限", "date": "2026-10-01", "token": "demo-b",
     "sources": ["policy-b-current"]},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path(".learning-labs/docpilot-eval.jsonl"))
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("trials must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="evaluation-") as directory:
        url = database_url(Path(directory) / "trial.sqlite")
        migrate(url)
        seed(url)
        with TestClient(create_app(url, tokens={"demo-a": "tenant-a", "demo-b": "tenant-b"})) as client:
            with args.output.open("w", encoding="utf-8") as report:
                for case in CASES:
                    for trial in range(args.trials):
                        start = perf_counter()
                        response = client.post("/api/questions", headers={"Authorization": "Bearer " + case["token"]},
                                               json={"question": case["question"], "as_of": case["date"]})
                        result = response.json()
                        found = {item["source_id"] for item in result.get("citations", [])}
                        expected = set(case["sources"])
                        coverage = expected <= found if expected else not found and result.get("needs_review") is True
                        record = {"suite": "docpilot-reference-v1", "grader": "source-coverage-v1",
                                  "case": case["id"], "trial": trial + 1, "status": response.status_code,
                                  "input": {"question": case["question"], "as_of": case["date"],
                                            "tenant": "tenant-a" if case["token"] == "demo-a" else "tenant-b"},
                                  "elapsed_ms": round((perf_counter() - start) * 1000, 2),
                                  "required_sources": sorted(expected), "cited_sources": sorted(found),
                                  "source_coverage_passed": response.status_code == 200 and coverage,
                                  "manual_semantic_grade": None, "result": result}
                        report.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Saved {len(CASES) * args.trials} attempts to {args.output}; grade semantic support manually")


if __name__ == "__main__":
    main()
