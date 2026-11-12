"""Arithmetic feedback for fictional case materials, not a design quality grader."""
import csv
import json
from collections import Counter
from pathlib import Path


def calculate(root=Path(__file__).parent):
    with (root / "observations.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    observations = {}
    for method in ("legacy", "prototype"):
        selected = [row for row in rows if row["method"] == method]
        observations[method] = {
            "attempts": len(selected),
            "completed": sum(row["correct"] == "1" and row["source_opened"] == "1" for row in selected),
            "independent": sum(row["correct"] == "1" and row["source_opened"] == "1" and
                               row["help_count"] == "0" for row in selected),
        }
    loads = {}
    for line in (root / "load.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        loads.setdefault(row["scenario"], Counter())[row["outcome"]] += 1
    with (root / "costs.csv").open(encoding="utf-8", newline="") as stream:
        costs = list(csv.DictReader(stream))
    revenue = sum(int(row["amount_yuan"]) for row in costs if row["kind"] == "revenue")
    variable = sum(int(row["amount_yuan"]) for row in costs if row["kind"] == "variable")
    onboarding = sum(int(row["amount_yuan"]) for row in costs if row["kind"] == "onboarding")
    return {"fictional": True, "observations": observations, "request_counts": loads,
            "monthly_contribution_yuan": revenue - variable,
            "first_month_contribution_yuan": revenue - variable - onboarding,
            "cash_flow": "unknown: payment dates and other costs missing"}


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
