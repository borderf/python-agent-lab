"""Run the chapter 7 order report CLI against a JSONL file."""

import argparse
import json
import os
from pathlib import Path
import sys

from .orders_core import load_orders, report


def save_report(path, result):
    payload = json.dumps(result, ensure_ascii=False)
    target = Path(path)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成订单报告")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = report(load_orders(args.input))
        payload = save_report(args.output, result)
    except (OSError, ValueError) as exc:
        print(f"失败:{exc}", file=sys.stderr)
        return 1
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())