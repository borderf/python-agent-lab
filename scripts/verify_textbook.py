"""Check textbook structure and execute explicitly identified offline examples.

Run from the repository root: python scripts/verify_textbook.py
Use --static-only for structure/syntax/links without executing any examples.
Framework examples are parsed, never executed or installed by this tool.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "docs" / "python-book"
SECTIONS = ["学习目标与前置知识", "基础知识讲解", "原理讲解与推导", "示例与逐步走查",
            "动手练习", "验收与自测", "面试问答与迁移", "本章小结与参考"]


def anchors(text: str) -> set[str]:
    result: set[str] = set()
    used: Counter[str] = Counter()
    for heading in re.findall(r"^#{1,6} (.+)$", text, re.M):
        plain = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", plain.lower()).replace(" ", "-")
        suffix = f"-{used[slug]}" if used[slug] else ""
        result.add(slug + suffix)
        used[slug] += 1
    return result


def verify(static_only: bool) -> dict:
    failures: list[str] = []
    chapters = sorted(p for p in BOOK.glob("[0-9][0-9]-*.md") if not p.name.startswith("00-"))
    python_blocks = json_blocks = links = anchor_links = frameworks = 0
    identifiers: list[str] = []
    labs: list[str] = []
    runnable: list[tuple[str, str]] = []
    pytest_examples: list[tuple[str, str]] = []
    for path in chapters:
        text = path.read_text(encoding="utf-8")
        expected = [(str(i), title) for i, title in enumerate(SECTIONS, 1)]
        if re.findall(r"^## (\d+)\. (.+)$", text, re.M) != expected:
            failures.append(f"{path.name}: eight-section structure")
        if text.count("**本章从这里开始：**") != 1:
            failures.append(f"{path.name}: missing or duplicate opening")
        if text.count("<details>") != 1 or text.count("</details>") != 1:
            failures.append(f"{path.name}: missing or duplicate self-check")
        if len(re.findall(r"^#### 案例推进：", text, re.M)) < 3:
            failures.append(f"{path.name}: incomplete worked learning sequence")
        numbers = re.findall(r"^### (\d+\.\d+) ", text, re.M)
        if len(numbers) != len(set(numbers)):
            failures.append(f"{path.name}: duplicate subsection number")
        labs.extend(re.findall(r"^### (L\d{2})：", text, re.M))
        basics = re.search(r"## 2\. 基础知识讲解\n(.*?)(?=## 3\.)", text, re.S)
        for index, code in enumerate(re.findall(r"```python\n(.*?)```", text, re.S), 1):
            python_blocks += 1
            label = f"{path.name}:block-{index}"
            try:
                tree = ast.parse(code, filename=label)
            except SyntaxError as exc:
                failures.append(f"{label}: {exc}")
                continue
            marker = re.search(r"# (?:experiment|book-example|study-example|framework-example|pytest-example): ([A-Z]\d{2}[A-Z]?)", code)
            if marker:
                identifier = marker.group(1)
                identifiers.append(identifier)
                label = f"{path.name}:{identifier}"
            else:
                identifier = ""
            if "# framework-example:" in code:
                frameworks += 1
            elif "# pytest-example:" in code:
                pytest_examples.append((label, code))
            elif identifier or (basics and code in basics.group(1)):
                runnable.append((label, code))
            else:
                frameworks += 1
            # Early language chapters must not depend on function/class definitions.
            if int(path.name[:2]) <= 3 and any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for node in ast.walk(tree)):
                failures.append(f"{label}: function/class used before the function chapter")
        for code in re.findall(r"```json\n(.*?)```", text, re.S):
            json_blocks += 1
            try:
                json.loads(code)
            except ValueError as exc:
                failures.append(f"{path.name}: JSON {exc}")
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")),
                      *sorted((ROOT / "practice").rglob("*.md"))]
    for path in markdown_files:
        prose = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        prose = re.sub(r"`[^`\n]*`", "", prose)
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", prose):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            file_name, _, fragment = unquote(target).partition("#")
            destination = (path.parent / file_name).resolve() if file_name else path
            links += 1
            if not destination.exists():
                failures.append(f"{path.name}: missing {target}")
            elif fragment and destination.suffix == ".md":
                anchor_links += 1
                if fragment not in anchors(destination.read_text(encoding="utf-8")):
                    failures.append(f"{path.name}: missing anchor {target}")
    if len(chapters) != 30:
        failures.append("expected 30 chapters")
    for prefix, expected in [("E", {f"E{i:02d}" for i in range(1, 25)}),
                             ("B", {f"B{i:02d}" for i in range(1, 13)} | {"B18", "B20", "B21", "B26"})]:
        if {key for key in identifiers if key.startswith(prefix)} != expected:
            failures.append(f"{prefix} examples incomplete")
    if sorted(labs) != [f"L{i:02d}" for i in range(1, 25)]:
        failures.append("L01-L24 missing or duplicated")
    if len(identifiers) != len(set(identifiers)):
        failures.append("duplicate code identifier")
    passed = pytest_passed = 0
    if not static_only and not failures:
        with TemporaryDirectory(prefix="textbook-check-") as directory:
            for label, code in runnable:
                try:
                    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=directory,
                                            capture_output=True, text=True, encoding="utf-8", timeout=20)
                    if result.returncode:
                        failures.append(f"{label}: {result.stderr[-1400:]}")
                    else:
                        passed += 1
                except subprocess.TimeoutExpired:
                    failures.append(f"{label}: timeout")
            for index, (label, code) in enumerate(pytest_examples):
                test_file = Path(directory) / f"test_textbook_{index}.py"
                test_file.write_text(code, encoding="utf-8")
                result = subprocess.run([sys.executable, "-m", "pytest", str(test_file), "-q"], cwd=directory,
                                        capture_output=True, text=True, encoding="utf-8", timeout=30)
                if result.returncode:
                    failures.append(f"{label}: {result.stdout[-1000:]} {result.stderr[-1000:]}")
                else:
                    match = re.search(r"(\d+) passed", result.stdout)
                    pytest_passed += int(match.group(1)) if match else 0
    return {
        "python": sys.version.split()[0], "chapters":len(chapters), "python_blocks":python_blocks,
        "json_blocks":json_blocks, "local_links":links, "anchor_links":anchor_links,
        "offline_examples":len(runnable), "offline_passed":passed,
        "pytest_example_files":len(pytest_examples), "pytest_cases_passed":pytest_passed,
        "framework_syntax_only":frameworks, "static_only":static_only,
        "example_sha256":hashlib.sha256("\n".join(label+code for label,code in runnable+pytest_examples).encode()).hexdigest(),
        "failures":failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    report = verify(args.static_only)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(report["failures"])


if __name__ == "__main__":
    raise SystemExit(main())
