# 第12章　Python 综合项目与独立验收

[上一章](11-异步、线程进程与性能边界.md) · [全书目录](教材目录.md) · [下一章](13-环境、分层、配置与工程交付.md)
## 1. 学习目标与前置知识

前置：第1–11章。本章不引入新框架，只把订单规则、文件入口、异步查询和测试组装成一个可安装项目。
**任务卡**
- 接收：第7章的 `orders_core.py`、`report_cli.py`，第11章的 `queries.py` 和测试。
- 只新增：`order-service/` 项目骨架、统一 `build_report`、`order-report` 入口与可编辑安装。
- 交付：源码、固定 JSONL、测试、安装命令和一次正常/失败运行记录。
- 验收：在独立虚拟环境可编辑安装；CLI 正常退出并生成报告，冲突或坏行非零退出且保留旧报告。
**本章从这里开始：** 单文件示例都能运行，但换一个入口或输入就可能重复计金额、覆盖旧报告。现在用一条固定数据流把它们组合起来，并让另一个人按命令复现。
## 2. 基础知识讲解
### 2.1 先固定订单契约

每条订单只有 `id/user/amount_cents/status` 四个字段。`id/user` 去两端空白后必须非空；金额是非负整数且拒绝 `bool`；状态为 `paid/pending/cancelled`。同 ID 完全重复保留首条，同 ID 内容冲突则整批失败。

报告固定为 `input_count/order_count/paid_amount_cents`。空输入返回三个 0；字段错误保留行号或字段名；冲突不能伪装成空报告。
#### 案例推进：先规范化，再去重，最后汇总
```python
# study-example: S12A
def normalize(raw):
    result = []
    for row in raw:
        clean = dict(row)
        clean["id"] = row["id"].strip()
        if not clean["id"] or type(row["amount_cents"]) is not int or row["amount_cents"] < 0:
            raise ValueError("非法订单")
        result.append(clean)
    return result
def unique(rows):
    by_id = {}
    for row in rows:
        if row["id"] in by_id and by_id[row["id"]] != row:
            raise ValueError("订单冲突")
        by_id.setdefault(row["id"], row)
    return list(by_id.values())
raw = [{"id": " A ", "amount_cents": 1990, "status": "paid"},
       {"id": "A", "amount_cents": 1990, "status": "paid"}]
rows = unique(normalize(raw))
assert len(rows) == 1 and sum(row["amount_cents"] for row in rows) == 1990
assert raw[0]["id"] == " A "
```

这是最小数据流探针，完整项目还要检查字段集合、用户、状态和错误位置。先统计再去重会把 1990 错算成 3980。
### 2.2 入口、业务和输出各负一项责任

CLI 解析参数和文件，业务函数校验、去重、汇总，输出函数负责编码与原子替换。异步查询只返回原始订单，不自己计算金额。这样文件、查询和后面的 HTTP 入口可以复用同一规则。

资源责任也要明确：输入文件由 `with` 关闭；输出先写同目录临时文件，全部成功后再替换目标；失败时删除本次临时文件并保留旧报告。
临时替换保证的是单机文件在一次成功发布时的完整性，不保证文件与数据库同时提交。若后续引入数据库，需要额外定义恢复与对账，不能沿用“换文件”作为分布式事务。
### 2.3 可编辑安装与 wheel 是两种验收

本章使用 `pip/uv` 的可编辑安装，让新虚拟环境能找到 `order-report` 入口；它仍指向当前源码，适合开发。wheel 是独立安装产物，第13章再构建并放到非源码目录验证。两种证据不能互相替代。
### 2.4 用需求—验收矩阵组织四类证据

先让每条需求都有可观察的验收条件，再选测试和命令；不要从“已经写了哪些测试”反推需求覆盖。

| 需求或契约 | 正常证据 | 边界证据 | 失败证据 | 副作用证据 |
| --- | --- | --- | --- | --- |
| 订单报告 | A 的 paid 金额为 1990 | 空文件、完全重复、两端空白 | 坏 JSON、同 ID 冲突非零退出 | 输入不变，旧报告不被失败覆盖 |
| CLI 与安装 | 项目外目录能发现入口并退出 0 | 绝对路径、空白行、省略可选参数仍成功 | 缺输入、非法参数有明确错误 | 仅目标报告变化，临时文件被清理 |
| 异步查询接入 | 多用户结果保持输入顺序 | 空列表、重复用户、达到并发上限 | 超时或下游失败可区分 | 无遗留任务，失败不产生半份报告 |

“正常”证明主路径，“边界”证明输入极限，“失败”证明错误语义，“副作用”证明文件、网络、数据库或任务没有越权。四类证据互相不能替代：退出码为 0 不代表没有多写文件，业务断言通过也不代表安装入口可用。

变更先映射到契约，再决定测试范围：改字段规则要同步规范化、冲突判断、固定数据和全链测试；改 CLI 参数要覆盖解析与集成；改打包入口要在干净环境重新安装。未被触及的公共契约仍跑回归，不能只重跑离改动最近的一个函数。

独立实现先用矩阵和失败样例约束行为，再对照参考代码解释差异；照抄参考不算独立完成。行为相同可以保留不同实现，参考暴露遗漏时则修改实现或测试并记录理由，而不是为了对齐而删除反例。

安装验收至少从项目外的空工作目录执行入口。可编辑安装仍使用源码，不能据此证明 wheel 自包含；第13章用 `dist` 产物重复验收。输入、输出和解释器均用绝对路径，避免验证的是当前目录恰好提供的导入或文件。
## 3. 原理讲解与推导
### 3.1 正确汇总来自不可交换的处理顺序

字段规范化决定哪些记录算重复；去重决定金额出现几次；汇总只消费已去重记录。若交换顺序，局部函数仍可能正确，整条链却重复计数。因此每一层都要写明前置条件与输出契约，组合测试使用同一份固定数据贯穿全链。
## 4. 示例与逐步走查
### 4.1 写统一业务函数
#### 案例推进：从原始行生成报告

把下面保存为 `src/order_service/core.py`。它接收可迭代的原始字典，因此文件加载器和异步查询都能接入。
```python
# book-example: B12
FIELDS = {"id", "user", "amount_cents", "status"}
STATUSES = {"paid", "pending", "cancelled"}
class OrderConflict(ValueError):
    pass
def normalize(row):
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError("订单字段必须恰好是 id/user/amount_cents/status")
    for field in ("id", "user"):
        if not isinstance(row[field], str) or not row[field].strip():
            raise ValueError(f"{field} 必须是非空文本")
    if type(row["amount_cents"]) is not int or row["amount_cents"] < 0:
        raise ValueError("amount_cents 必须是非负整数分")
    if not isinstance(row["status"], str) or row["status"] not in STATUSES:
        raise ValueError("非法订单状态")
    return {"id": row["id"].strip(), "user": row["user"].strip(),
            "amount_cents": row["amount_cents"], "status": row["status"]}
def build_report(raw_rows):
    by_id, input_count = {}, 0
    for line_number, raw in enumerate(raw_rows, 1):
        input_count += 1
        try:
            row = normalize(raw)
        except ValueError as exc:
            raise ValueError(f"第{line_number}条: {exc}") from exc
        if row["id"] in by_id and by_id[row["id"]] != row:
            raise OrderConflict(f"第{line_number}条: 订单冲突:{row['id']}")
        by_id.setdefault(row["id"], row)
    return {"input_count": input_count, "order_count": len(by_id),
            "paid_amount_cents": sum(row["amount_cents"] for row in by_id.values()
                                     if row["status"] == "paid")}
```
### 4.2 接文件入口并声明安装信息
#### 案例推进：失败时保留旧报告

保存为 `src/order_service/cli.py`；空 JSONL 行跳过，坏行带行号报错。
```python
import argparse
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from .core import build_report
def load_orders(path):
    with open(path, encoding="utf-8") as stream:
        for line_number, text in enumerate(stream, 1):
            if not text.strip():
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第{line_number}行不是合法JSON") from exc
def main(argv=None):
    parser = argparse.ArgumentParser(description="生成订单报告")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_report(load_orders(args.input))
        payload = json.dumps(result, ensure_ascii=False)
        target = Path(args.output)
        temporary = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                    prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        print(f"失败:{exc}", file=sys.stderr)
        return 1
    print(payload)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
```

项目骨架与 `pyproject.toml` 如下；`src/order_service/__init__.py` 留空即可。
```toml
[build-system]
requires = ["uv_build>=0.12.17,<0.13.0"]
build-backend = "uv_build"

[project]
name = "order-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
order-report = "order_service.cli:main"

[dependency-groups]
dev = ["pytest>=9.1.1"]
```
### 4.3 用固定数据完成安装验收
#### 案例推进：先正常，再把最后一条改成冲突

`data/orders.jsonl` 放三条记录：A/Alice/1990/paid、B/Bob/1000/pending、与 A 完全相同的一条。先在项目根确定绝对路径，再切到项目外新建的空目录执行；输入、输出和解释器都不依赖当前源码目录。

```powershell
$project = (Resolve-Path ".").Path
$work = Join-Path $env:TEMP ("order-report-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory $work | Out-Null
uv venv "$work/.venv"
uv pip install --python "$work/.venv/Scripts/python.exe" -e $project
Push-Location $work
try {
    & "$work/.venv/Scripts/order-report.exe" (Join-Path $project "data/orders.jsonl") --output (Join-Path $work "report.json")
} finally {
    Pop-Location
}
```

正常报告应为 `{"input_count": 3, "order_count": 2, "paid_amount_cents": 1990}`。把第三条 A 的金额改为 1991，再运行同一命令：应非零退出，stderr 含冲突，`report.json` 仍是上一次成功内容。这里验证的是可编辑安装，不是 wheel 内容完整性。
空文件应得到三个 0；空白行不计入 `input_count`，但合法 JSON 的每一行都计入。损坏末行发生在报告计算和替换之前，因此旧报告与输入文件都不会被本次失败改写。
### 4.4 选读：模式匹配与海象表达式

订单项目不需要这两种语法。理解 `match` 后，可以用它重写按类型分支的入口；下面保留原 `S04G` 实验，它不改变前面的数据流。

```python
# study-example: S04G
payload = {"type": "query", "limit": 3}
match payload:
    case {"type": "query", "limit": limit} if type(limit) is int and limit > 0:
        action = "查询"
    case _:
        action = "拒绝"
assert action == "查询"
raw = " Alice "
if (name := raw.strip()):
    assert name == "Alice"
```

## 5. 动手练习
### 本章累计任务：独立交付订单程序

把第7章入口整理为上述项目，并把第11章查询返回的原始订单交给 `build_report`。测试空输入、完全重复、同 ID 冲突和损坏末行；完成可编辑安装后记录正常与失败命令、退出码和报告内容。不要新增 HTTP 或数据库。
## 6. 验收与自测
**验收产物：** 新虚拟环境中的 `order-report` 入口，以及正常/冲突两次运行记录；冲突运行不得改写旧 `report.json`。
### 6.1 先预测，再查看参考推导

为什么单元测试都通过，仍要跑一次“文件→校验→去重→汇总→替换输出”的完整链路？
<details>
<summary>完成预测后查看解释</summary>

组合错误常发生在契约衔接处，例如单位不一致、先去重后统计或失败后覆盖输出。完整链路用固定数据检查这些前后条件，也能发现入口和资源管理问题。

</details>
## 7. 面试问答与迁移
**问：怎样说明项目不是只会跑示例？**
答：换一份未见输入，从安装入口运行到报告，再制造冲突和坏行；解释首次失败位置、退出码和旧报告为何保留。证据要覆盖正常与失败路径。
**问：为什么本章不用 wheel 验收？**
答：可编辑安装验证入口、依赖声明和开发环境能否找到项目；wheel 还要验证打包内容与源码解耦。第13章在干净环境完成后者，避免两种失败混在一起。
## 8. 本章小结与参考

- 统一契约：严格字段、规范化、去重、整数分汇总。
- 统一数据流：所有入口把原始订单交给同一个 `build_report`。
- 明确资源责任：失败不覆盖旧报告，临时文件必须清理。
- 本章交付可编辑安装的订单项目，第13章增加可复现环境与 wheel。

参考：[Python 打包](https://packaging.python.org/en/latest/tutorials/packaging-projects/)、[uv 项目](https://docs.astral.sh/uv/guides/projects/)。

[上一章](11-异步、线程进程与性能边界.md) · [下一章](13-环境、分层、配置与工程交付.md)
