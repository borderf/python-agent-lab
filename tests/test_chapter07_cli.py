"""Chapter 7's real CLI must run, fail cleanly, and preserve the old report."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "practice/chapter_labs/ch07_report/data"


def run(input_path, output_path):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "practice.chapter_labs.ch07_report.report_cli",
         str(input_path), "--output", str(output_path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20)


def test_normal_input_writes_report(tmp_path):
    output = tmp_path / "report.json"
    result = run(DATA / "orders.jsonl", output)
    assert result.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "order_count": 2, "paid_amount_cents": 1990}


def test_bad_last_line_keeps_old_report(tmp_path):
    output = tmp_path / "report.json"
    output.write_text('{"old":true}', encoding="utf-8")
    result = run(DATA / "bad.jsonl", output)
    assert result.returncode == 1
    assert "第2行" in result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}


def test_conflict_keeps_old_report(tmp_path):
    output = tmp_path / "report.json"
    output.write_text('{"old":true}', encoding="utf-8")
    result = run(DATA / "conflict.jsonl", output)
    assert result.returncode == 1
    assert "冲突:A" in result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}


def test_missing_parent_returns_one(tmp_path):
    result = run(DATA / "orders.jsonl", tmp_path / "missing" / "report.json")
    assert result.returncode == 1
    assert "失败" in result.stderr


def test_invalid_records_are_rejected(tmp_path):
    cases = {
        "null": "null\n",
        "number": "1\n",
        "list-id": '{"id":[],"user":"Alice","amount_cents":1,"status":"paid"}\n',
        "empty-id": '{"id":" ","user":"Alice","amount_cents":1,"status":"paid"}\n',
        "empty-user": '{"id":"A","user":" ","amount_cents":1,"status":"paid"}\n',
        "bad-status": '{"id":"A","user":"Alice","amount_cents":1,"status":"paidd"}\n',
        "list-status": '{"id":"A","user":"Alice","amount_cents":1,"status":[]}\n',
    }
    for name, text in cases.items():
        source = tmp_path / f"{name}.jsonl"
        source.write_text(text, encoding="utf-8")
        output = tmp_path / f"{name}.json"
        output.write_text('{"old":true}', encoding="utf-8")
        result = run(source, output)
        assert result.returncode == 1, name
        assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}, name