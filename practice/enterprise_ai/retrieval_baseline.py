"""离线检索实验。题目中的身份与日期由评测夹具指定。"""

import argparse
from collections.abc import Callable
import json
from pathlib import Path
from statistics import mean


DATA = Path(__file__).with_name("data")
TOP_K = 5


def bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)}


def eligible_sources(policies: list[dict], tenant: str, date: str) -> list[dict]:
    # 夹具使用固定宽度的 ISO 日期，结束日不再有效。
    return [
        row for row in policies
        if row["tenant_id"] == tenant and row["valid_from"] <= date
        and (row["valid_to"] is None or date < row["valid_to"])
        and row.get("trusted_policy", True)
    ]


def rank_sources(query: str, sources: list[dict], method: str) -> list[str]:
    if method == "blind":
        return sorted(row["source_id"] for row in sources)
    terms = bigrams(query)
    scored = []
    for row in sources:
        words = bigrams(row["title"]) | bigrams(row["section"]) | bigrams(row["text"])
        overlap = len(terms & words)
        scored.append((-overlap, row["source_id"]))
    return [source_id for _, source_id in sorted(scored)]


def evaluate(policies: list[dict], cases: list[dict], method: str,
             ranker: Callable[[str, list[dict]], list[str]] | None = None) -> None:
    recall_scores = []
    reciprocal_ranks = []
    for case in cases:
        relevant = set(case["expected_source_ids"])
        if not relevant:
            continue  # 无答案、越权和不可信附件另在应用层做行为验收。
        visible = eligible_sources(policies, case["tenant_id"], case["as_of"])
        ranking = ranker(case["query"], visible) if ranker else rank_sources(case["query"], visible, method)
        authorized = {row["source_id"] for row in visible}
        if len(set(ranking)) != len(ranking) or not set(ranking) <= authorized or not relevant <= authorized:
            raise ValueError(f"检查来源标识、权限、日期或标注: {case['case_id']}")
        if len(visible) <= TOP_K:
            raise ValueError(f"候选不足以比较 Recall@{TOP_K}: {case['case_id']}")
        top = ranking[:TOP_K]
        recall = len(relevant.intersection(top)) / len(relevant)
        first = next((i for i, item in enumerate(top, 1) if item in relevant), None)
        recall_scores.append(recall)
        reciprocal_ranks.append(1 / first if first else 0.0)
        print(f"{case['case_id']:24} n={len(visible)} recall={recall:.2f} "
              f"first={first or '-'} top={','.join(top)}")
    print(f"{method}: n={len(recall_scores)} Recall@5={mean(recall_scores):.3f} "
          f"MRR@5={mean(reciprocal_ranks):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    args = parser.parse_args()
    policies = json.loads((DATA / "policies.json").read_text(encoding="utf-8"))
    cases = json.loads((DATA / "retrieval_cases.json").read_text(encoding="utf-8"))
    selected = [case for case in cases if case.get("split", "dev") == args.split]
    for method in ("blind", "bigram"):
        evaluate(policies, selected, method)


if __name__ == "__main__":
    main()
