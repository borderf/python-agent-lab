# Python → AI 应用：可练习教程

适用对象：有 Java 后端基础，正在学习 Python，希望开发 AI 应用的你。教程以当前订单项目为主线，按四个主题阶段、20 课组织。这里的“周”代表主题，一课可以分成 1–3 次学习，不要求四个自然周学完。

长期执行参照 [16 周项目主线](../learning-plan/enterprise-ai-16-weeks.md)，基础需要展开时使用 [8 周学习过程](../learning-plan/study-process.md)，两者不同时推进。官方教程为阅读主线，Python-100-Days 为补充练习，本文和 practice 目录为配套教材。下表的四个“周”是原来的主题标签，文件名不代表长期主线的日历周数。

## 从哪里开始

| 阶段 | 教程 | 课程与成果 |
| --- | --- | --- |
| 第一周 | [Python 与订单分析](01-python-orders.md) | 01–05：变量与对象、集合、函数、金额、文件；做出 JSON 订单报告 |
| 第二周 | [工程基础与 HTTP](02-engineering-http.md) | 06–10：模块、校验、测试、HTTP、配置与日志；做出可测试的数据客户端 |
| 第三周 | [异步与 FastAPI](03-async-api.md) | 11–15：协程、并发限制、超时取消、接口与集成；做出订单分析服务 |
| 第四周 | [模型与工具调用](04-model-agent.md) | 16–20：模型适配、结构化结果、工具、循环与评估；做出订单助手 |

你当前已写过集合函数和类型标注。可以先自查第 01–02 课，重点补第 03 课整数分、第 04 课重复冲突，以及第 05 课 JSON。原有 [第一周计划](../learning-plan/week-01.md) 是每日安排，这里的第一阶段进一步解释相关原理和练习；课程编号与旧计划的 Day 编号不一一对应。

## 练习区与命令

起始代码位于 [practice/python_ai_course](../../practice/python_ai_course/README.md)，现有 src 中的练习保留。起始代码包含明确的 TODO 和 NotImplementedError，供你自己完成；它们不是已经实现的功能。

在项目根目录使用 PowerShell：

```powershell
uv sync
uv run python --version
uv run python -X utf8 -m practice.python_ai_course.preflight
# 每完成一项，运行对应的验收案例；未实现时失败是正常反馈。
uv run python -m pytest practice/python_ai_course/checks_week01.py -q
# 也可以只检查一类功能。
uv run python -m pytest practice/python_ai_course/checks_week01.py -q -k money
```

练习检查文件叫 checks_weekXX.py，需要显式指定路径；普通的 `uv run pytest` 不会默认收集这些未完成练习。已有项目测试仍在 tests/ 下。验收案例用于明确需求，不能代表覆盖了所有错误；每课还有需要你自行补充的案例。

第一周使用标准库和项目已有 pytest。进入第二周再按该章命令添加依赖。本教程没有替你安装依赖、下载模型或调用收费服务。模型阶段先用离线假模型练习流程，再连接你选择的真实模型。

## 统一数据与业务规则

订单结构在所有阶段保持一致：

```python
{"id": "10001", "user": "Alice", "amount_cents": 19900, "status": "paid"}
```

- 字段恰好为 id、user、amount_cents、status；额外字段也拒绝，便于观察契约是否一致。
- id、user 必须是字符串，去掉两端空白后不能为空；保留大小写。用户名称比较区分大小写。
- amount_cents 是非负整数，拒绝 float、数字字符串和 bool；Python 中 bool 是 int 的子类，校验时要注意。
- 状态只能是 paid、pending、cancelled。
- 完全相同的重复 ID 保留首条；同 ID 任一字段不一致，抛出 ValueError；输出保持首次出现的顺序。
- 报告流程为：读取 → 校验与规范化 → 去重 → 汇总 → 展示。金额并列排序保持原相对顺序。
- 所有业务函数不修改输入列表及内部订单字典；允许返回新列表引用原订单，调用方也应避免通过结果修改输入。
- 校验失败报错，不静默跳过坏记录，不把网络失败伪装成空订单。

这些是本练习的约定。真实业务可以采用其他规则，但要同步修改文档、实现和测试。

基础数据：[orders.json](../../practice/python_ai_course/data/orders.json)。预期报告为：

```json
{
  "input_count": 4,
  "order_count": 4,
  "paid_count": 2,
  "total_amount_cents": 129600,
  "paid_amount_cents": 79800,
  "paid_amount_by_user": {"Alice": 79800, "Bob": 0, "Tom": 0}
}
```

input_count 是去重前的合法记录数，order_count 是去重后的订单数；两个金额都在去重后统计。重复样例会令 input_count 变成 5，其余字段不变。

## 每课怎么学

1. 先阅读“理解”和短示例，用自己的话解释输出。
2. 按需求独立写 15–20 分钟，卡住再看提示或官方文档。
3. 运行指定检查；先核对输入与预期，再修改实现。
4. 自己补一条反例，解释它能发现什么错误。
5. 在 [学习记录模板](learning-log.md) 中记录问题、原因与完成证据。

验收不是看过视频或敲过示例：你应能合上资料重写关键代码，解释一个边界，并修改需求后同步调整测试。

## 参考资料的用法

语雀课程可作为中文辅助阅读，本文不对整套课程质量作统一评分。已经核对的 [变量与逻辑控制](https://www.yuque.com/lianlianfengchen-cvvh2/aoy8p0/de8cuo8rg9vh7esy) 适合快速复习；注意三引号是字符串，eval 会执行表达式，格式化两位小数不会修复浮点误差。其他课程章节可在遇到对应主题时选读。

核心依据为 [Python 3.12 教程](https://docs.python.org/3.12/tutorial/)、[uv 项目指南](https://docs.astral.sh/uv/guides/projects/)、[pytest 文档](https://docs.pytest.org/en/stable/)。第二至四周的官方资料在对应章节列出。只读当天练习需要的部分；数据库、复杂魔法方法和多进程原理可以在项目出现需要时再补。
