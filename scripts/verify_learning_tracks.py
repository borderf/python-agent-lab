"""Check both learning tracks and their explicitly selected local exercises.

The existing textbook checker validates repository-wide Markdown links.
This tool adds structure/syntax for the independent books and exercises.
"""

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

from verify_textbook import verify as verify_original


ROOT = Path(__file__).resolve().parents[1]
BOOKS = ("architecture-book", "product-founder-book")
SECTION_NAMES = (
    "目标、前置与问题", "概念与基础", "机制与推导", "案例逐步推演",
    "分层练习", "自测与参考推导", "项目交付与验收", "迁移与阅读",
)
EXERCISES = (
    "practice/enterprise_ai/retrieval_baseline.py",
    "practice/architecture_labs/idempotency_sqlite.py",
    "practice/product_labs/metrics_and_cost.py",
    "practice/product_labs/search_slice/checks.py",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    original = verify_original(static_only=True)
    failures = list(original["failures"])
    chapters_by_book = {}
    examples = []
    example_ids = set()
    for name in BOOKS:
        folder = ROOT / "docs" / name
        chapters = sorted(p for p in folder.glob("[0-9][0-9]-*.md")
                          if not p.name.startswith("00-"))
        chapters_by_book[name] = len(chapters)
        if [int(p.name[:2]) for p in chapters] != list(range(1, 15)):
            failures.append(f"{name}: expected unique chapters 01-14")
        for path in folder.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if text.count("```") % 2:
                failures.append(f"{path.name}: unmatched code fence")
            if path not in chapters:
                continue
            expected = [(str(i), title) for i, title in enumerate(SECTION_NAMES, 1)]
            if re.findall(r"^## (\d+)\. (.+)$", text, re.M) != expected:
                failures.append(f"{path.name}: section structure")
            if text.count("<details>") != 1 or text.count("</details>") != 1:
                failures.append(f"{path.name}: self-check")
            subsections = re.findall(r"^### (\d+\.\d+) ", text, re.M)
            if len(subsections) != len(set(subsections)):
                failures.append(f"{path.name}: duplicate subsection")
            for code in re.findall(r"```python\n(.*?)```", text, re.S):
                try:
                    ast.parse(code, filename=str(path))
                except SyntaxError as error:
                    failures.append(str(error))
                marker = re.search(r"^# track-example: ([AP]\d{2})$", code, re.M)
                if marker:
                    identifier = marker.group(1)
                    if identifier in example_ids:
                        failures.append(f"duplicate track example: {identifier}")
                    example_ids.add(identifier)
                    examples.append((f"{name}:{identifier}", code))
    for area in ("enterprise_ai", "architecture_labs", "product_labs", "integration_labs"):
        for path in (ROOT / "practice" / area).rglob("*.py"):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as error:
                failures.append(str(error))
    passed = []
    examples_passed = []
    if not args.static_only and not failures:
        for label, code in examples:
            try:
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-c", code], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", timeout=20,
                )
                if result.returncode:
                    failures.append(f"{label}: {result.stderr[-1400:]}")
                else:
                    examples_passed.append(label)
            except subprocess.TimeoutExpired:
                failures.append(f"{label}: timeout")
        for filename in EXERCISES:
            try:
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", str(ROOT / filename)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
                )
                if result.returncode:
                    failures.append(f"{filename}: {result.stdout[-800:]} {result.stderr[-1600:]}")
                else:
                    passed.append(filename)
            except subprocess.TimeoutExpired:
                failures.append(f"{filename}: timeout")
    print(json.dumps({
        "chapters": chapters_by_book,
        "repository_local_links": original["local_links"],
        "repository_anchor_links": original["anchor_links"],
        "original_example_sha256": original["example_sha256"],
        "static_only": args.static_only, "exercises_passed": passed,
        "worked_examples_passed": examples_passed,
        "failures": failures,
        "not_verified": ["browser layout/interaction", "external services", "production", "real users"],
    }, ensure_ascii=False, indent=2))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
