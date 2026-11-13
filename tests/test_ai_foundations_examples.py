"""Execute the AI-foundations code blocks explicitly marked # runnable."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "docs" / "ai-foundations"


def test_runnable_ai_examples():
    executed = []
    for path in sorted(BOOK.glob("[0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        for index, code in enumerate(re.findall(r"```python\n(.*?)```", text, re.S), 1):
            if "# runnable" not in code:
                continue
            namespace = {"__name__": f"{path.stem}-{index}"}
            exec(compile(code, f"{path.name}:{index}", "exec"), namespace)
            executed.append(f"{path.name}:{index}")
    assert len(executed) >= 6, executed