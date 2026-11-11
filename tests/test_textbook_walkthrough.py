"""The code printed in chapter 23 must compose and meet learner contracts."""
from pathlib import Path
import re
import runpy
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def test_cumulative_docpilot_textbook_code_meets_contract():
    path = next((ROOT / "docs/python-book").glob("23-*.md"))
    text = path.read_text(encoding="utf-8").split("## 4. 示例与逐步走查", 1)[1].split("## 5. 动手练习", 1)[0]
    blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    assert len(blocks) == 4, "Four cumulative checkpoints must stay explicit"
    implementation = ModuleType("textbook_walkthrough")
    exec(compile("\n\n".join(blocks), str(path), "exec"), implementation.__dict__)
    contract = runpy.run_path(str(ROOT / "tests/learner/contract_docpilot.py"))
    checks = [contract[name] for name in sorted(contract) if re.match(r"test_s\d\d_", name)]
    assert len(checks) == 20
    for check in checks:
        check(implementation)


def test_cumulative_agent_textbook_code_meets_contract():
    path = next((ROOT / "docs/python-book").glob("24-*.md"))
    text = path.read_text(encoding="utf-8").split("### 4.2 从零 12 步", 1)[1].split("## 5. 动手练习", 1)[0]
    blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    assert len(blocks) == 4, "Four cumulative agent checkpoints must stay explicit"
    implementation = ModuleType("agent_walkthrough")
    exec(compile("\n\n".join(blocks), str(path), "exec"), implementation.__dict__)
    contract = runpy.run_path(str(ROOT / "tests/learner/contract_agent.py"))
    checks = [contract[name] for name in sorted(contract) if re.match(r"test_s\d\d_", name)]
    assert len(checks) == 12
    for check in checks:
        check(implementation)
