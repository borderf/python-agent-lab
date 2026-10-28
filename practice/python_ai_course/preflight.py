"""教程准备检查：仅展示解释器、样例和依赖状态，不代表练习已通过。"""

import importlib.util
import json
import sys
from pathlib import Path


def main() -> None:
    print(f"Python：{sys.version.split()[0]}")
    if sys.version_info < (3, 12):
        raise SystemExit("本课程需要 Python 3.12 或更新版本，请检查项目解释器。")

    data_path = Path(__file__).parent / "data" / "orders.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    print(f"样例位置：{data_path}")
    print(f"基础订单：{len(rows)} 条，文件可以读取")
    for module in ("pytest", "pydantic", "httpx", "fastapi", "uvicorn"):
        status = "已安装" if importlib.util.find_spec(module) else "尚未安装"
        print(f"{module}：{status}")

    print("\n第一周练习只需标准库和 pytest；其余库到对应章节再安装。")
    print("准备检查完成；TODO 实现和课程验收仍需要你完成。")
    print("先阅读 docs/tutorial/01-python-orders.md，完成第 01 课。")


if __name__ == "__main__":
    main()
