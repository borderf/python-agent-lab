"""Execute the AI-foundations code blocks explicitly marked # runnable."""

from contextlib import redirect_stdout
import io
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "docs" / "ai-foundations"


def runnable_blocks():
    for path in sorted(BOOK.glob("[0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        for index, code in enumerate(re.findall(r"```python\n(.*?)```", text, re.S), 1):
            if "# runnable" in code:
                yield path, index, code


def execute(code, filename):
    namespace = {"__name__": filename}
    output = io.StringIO()
    with redirect_stdout(output):
        exec(compile(code, filename, "exec"), namespace)
    return output.getvalue()


def test_runnable_ai_examples():
    executed = []
    for path, index, code in runnable_blocks():
        execute(code, f"{path.name}:{index}")
        executed.append(f"{path.name}:{index}")
    assert len(executed) >= 6, executed
    assert any(item.startswith("07-") for item in executed), executed
    assert any(item.startswith("09-") for item in executed), executed


def test_observation_examples_expose_input_intermediate_output_counterexample_and_metrics():
    for chapter in ("07-幻觉与RAG.md", "09-贯穿案例.md"):
        blocks = [(index, code) for path, index, code in runnable_blocks() if path.name == chapter]
        assert len(blocks) == 1, chapter
        output = execute(blocks[0][1], f"{chapter}:{blocks[0][0]}")
        for label in ("输入:", "中间结果:", "输出:", "反例:", "指标:"):
            assert label in output, (chapter, label, output)
