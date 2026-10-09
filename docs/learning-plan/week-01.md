# 第一周：Python 集合操作与订单分析

## 本周目标

在现有订单练习上，练习 Python 集合、函数、类型标注、异常、JSON 文件和基础测试。周末把练习整理成一个能从 JSON 读取订单并输出报告的小程序。

### 每天怎么安排

- Day 1–5：每天约 90 分钟。先回忆 10 分钟，读文档 20 分钟，动手 50 分钟，记录 10 分钟。
- Day 6：约 2 小时，完成文件读取和报告流程。
- Day 7：约 1–2 小时，自己验收、整理 README 和复盘。
- 每天先独立尝试 15–20 分钟，再查文档。不要整段复制教程代码；合上教程后重写一遍，并说明为什么这样写。
- 某天没有完成时，把内容顺延。不要为了赶日期跳过验收。

## 当前项目

- 练习代码：src/python_agent_lab/basics/collections.py
- 当前测试：tests/test_collections.py
- 运行练习：uv run python -m python_agent_lab.basics.collections
- 运行测试：uv run pytest

## Day 1：读懂集合操作，先定业务规则

### 学习目标

- 能说清 list、dict、set 各自适合保存什么数据。
- 能解释列表推导式和生成器表达式的差别。
- 能通过具体输入手算每个函数应该返回什么。

### 学习内容

1. 列表的创建、索引、遍历、追加和切片。
2. 字典的键和值、读取字段、遍历 items()。
3. 集合的唯一性、成员检查和去重用途。
4. 列表推导式：从一个可迭代对象筛选或转换数据。
5. 生成器表达式：逐项产生结果，常用于 sum() 等函数。
6. 函数的输入、输出和“不要悄悄改变输入”的约定。

### 动手练习

1. 从 collections.py 逐个读懂五个函数，不先修改代码。
2. 手算 get_paid_orders、calculate_total_amount、group_orders_by_user 的结果。
3. 在纸上或临时 Python 交互环境中写出：已支付订单 ID 列表、订单数量、平均订单金额。
4. 明确并记录以下规则：
   - 销售额统计所有订单，还是只统计已支付订单？
   - 相同 ID 的订单怎样判重？如果金额或状态不同，保留哪条或报错？
   - 空订单列表时，筛选、统计、分组、排序和去重分别返回什么？
   - 金额相同时排序要不要保持原顺序？

### 当日产出与验收

- 在本手册的“本周业务规则记录”区写下决定。
- 不看代码，能解释集合函数中输入、输出和边界情况。

### 学习资源

- [Python 官方教程：数据结构](https://docs.python.org/3.12/tutorial/datastructures.html)
- [Python 官方教程：循环与函数定义](https://docs.python.org/3.12/tutorial/controlflow.html#defining-functions)

## Day 2：给订单和函数添加类型标注

### 学习目标

- 看懂并编写常见函数签名，例如 list of Order 到 list of Order。
- 用 TypedDict 表达现有 JSON 字典的字段结构。
- 理解类型标注帮助 IDE 和静态检查工具发现问题；它本身不会校验运行时输入。

### 学习内容

1. 基本类型：str、int、float、bool。
2. 容器类型：list of Order、dict from string to list of Order、set of string。
3. 函数参数标注和返回值标注。
4. TypedDict 的必需字段。
5. Literal 表示有限状态，例如 paid、pending、cancelled。

### 动手练习

1. 在订单模块定义 OrderStatus 和 Order。
2. 先保留现有金额字段类型，避免同一天同时重构金额规则。
3. 为五个函数补上参数和返回值标注。
4. 故意把一个字段名拼错，观察编辑器是否能提示；随后改回正确写法。
5. 在注释中说明：从文件读入的外部数据仍需要运行时检查，TypedDict 不会替你验证 JSON。

订单类型可以先按下面的形状练习，不必照抄函数实现：

~~~python
from typing import Literal, TypedDict

OrderStatus = Literal["paid", "pending", "cancelled"]


class Order(TypedDict):
    id: str
    user: str
    amount: float
    status: OrderStatus


def get_paid_orders(orders: list[Order]) -> list[Order]:
    ...
~~~

### 当日产出与验收

- 订单字段和五个函数签名都有类型标注。
- 能解释 TypedDict 与运行时数据校验的区别。

### 学习资源

- [Python 3.12 typing：类型标注与 TypedDict](https://docs.python.org/3.12/library/typing.html)
- [Python 官方教程：类定义](https://docs.python.org/3.12/tutorial/classes.html)

## Day 3：金额统计与金额精度

### 学习目标

- 能用 sum() 和生成器表达式实现汇总。
- 知道二进制浮点数可能无法精确表示部分十进制小数。
- 能按已定义的业务规则计算金额。

### 学习内容

1. sum(iterable) 的输入和默认初始值。
2. 生成器表达式与列表推导式的使用场景。
3. 浮点数的近似表示问题。
4. 固定两位小数的货币可以用整数分保存；Decimal 是另一种常见表示方式。

### 原理讲解：sum() 如何汇总

`sum(iterable, start=0)` 接收一个可迭代对象，从 `start` 开始，把其中的值逐个相加。`start` 默认是整数 `0`，所以空输入也有确定结果：`sum([]) == 0`。例如：

~~~python
sum([10, 20, 30])  # 60
sum([])            # 0
~~~

这里的 `iterable` 不只可以是列表，也可以是生成器表达式。金额用整数“分”保存时，`sum()` 对整数做累加，结果仍然是整数分。

### 原理讲解：生成器表达式

生成器表达式的一般写法是：

~~~python
(表达式 for 临时变量 in 可迭代对象 if 条件)
~~~

它会按需产生值，而不是先把所有结果装进一个新列表。比如：

~~~python
amounts = (order["amount_cents"] for order in orders)
~~~

`amounts` 此时不是金额列表，而是一个可以逐项取值的生成器。它通常会在循环或 `sum()` 消费它时才计算下一项；被消费完以后就不能从头再读。生成器表达式和使用 `yield` 定义的生成器函数是两种相关但不同的写法；Day 3 只需掌握表达式。

列表推导式与生成器表达式的区别可以这样看：

~~~python
amounts_list = [order["amount_cents"] for order in orders]
total_a = sum(amounts_list)

total_b = sum(order["amount_cents"] for order in orders)
~~~

两种写法对这份数据会得到相同总额。第一种先创建一份新列表，再求和；第二种逐个把金额交给 `sum()`，不创建同规模的临时列表。订单很少时通常不必纠结速度；生成器表达式的主要学习价值是理解“按需产出”和减少中间列表。它不保证所有情况下运行得更快，也不适合需要反复读取同一批结果的场景。

### 套用到当前订单代码：从元 float 改成整数分

当前订单字段是 `amount: float`，例如 `199.0`。本练习把字段名和单位都明确下来，改成 `amount_cents: int`，并把 199 元存成 19900 分。需要同步修改以下位置，不能只改类型声明：

1. `Order` 中的字段：`amount: float` 改为 `amount_cents: int`。
2. `orders` 样例数据：每条记录的 `amount` 改为 `amount_cents`，金额乘 100 并写成整数，例如 `19900`。
3. 汇总函数：把名称改为能说明单位的名称，例如 `calculate_total_amount_cents`，返回类型改为 `int`，并读取 `amount_cents`。
4. 排序函数：排序键也改为读取 `amount_cents`；函数名可改成 `sort_orders_by_amount_cents`，让单位更清楚。
5. 测试或其他样例字典：如果还写着 `amount`，也一起改成 `amount_cents`。
6. 输出金额时再转换成人类可读格式。对于本练习的非负金额，可以用 `divmod(total_cents, 100)` 得到元和剩余分；存储和计算过程保持整数，不要先转成 `float`。

可以先参照下面的函数形状，自己把它放进订单模块并补齐另一个统计口径：

~~~python
def calculate_total_amount_cents(orders: list[Order]) -> int:
    return sum(order["amount_cents"] for order in orders)


def calculate_paid_amount_cents(orders: list[Order]) -> int:
    return sum(
        order["amount_cents"]
        for order in orders
        if order["status"] == "paid"
    )
~~~

第一个生成器表达式为每个订单产生一笔金额；第二个还带有 `if`，只为已支付订单产生金额。`sum()` 逐项消费这些金额，并把它们加起来。不要把所有订单金额都称作“销售额”：先明确“全部订单金额”和“已支付金额”的统计口径，再用函数名区分。

样例订单转换后，全部订单金额应为 `129600` 分，已支付金额应为 `79800` 分；订单数量分别为 4 和 2。空订单列表的总额和数量都应为 0。这些手算结果可以用来检查实现是否符合预期。

### 动手练习

1. 根据 Day 1 的决定，把总额函数名称或参数改到能准确表达统计口径。
2. 用整数分重写样例，例如 199 元保存为 19900 分；相应更新订单类型标注。
3. 实现总额和订单数量统计，至少分别处理“所有订单”和“已支付订单”这两种口径，或明确只支持其中一种。
4. 用手算结果核对函数返回值；金额展示时再转换成人类可读的元和分格式。
5. 加一个空列表例子，确认汇总结果符合你记录的规则。

### 当日产出与验收

- 金额存储规则已统一，销售额口径有明确名称或文档说明。
- 空列表和多个状态的汇总结果可以手算并验证。

### 学习资源

- [Python 官方教程：浮点数的限制](https://docs.python.org/3/tutorial/floatingpoint.html)
- [Python 内置函数：sum()](https://docs.python.org/3/library/functions.html#sum)
- [Python 官方教程：列表推导式和生成器表达式](https://docs.python.org/3/tutorial/datastructures.html#list-comprehensions)
- [Python 标准库：Decimal](https://docs.python.org/3/library/decimal.html)

## Day 4：去重、排序和输入数据边界

### 学习目标

- 能解释用 set 记录见过的订单 ID 的过程。
- 能区分完全重复记录和同 ID 冲突记录。
- 能检查函数有没有意外修改调用者传入的列表。

### 学习内容

1. 集合成员检查，例如 order_id in seen_ids。
2. sorted() 的 key 和 reverse 参数。
3. 列表遍历时创建新列表，与直接修改原列表的区别。
4. 缺少字段、错误金额类型、未知状态等数据边界。

### 动手练习

1. 为去重练习准备三组数据：不同 ID、内容完全相同的重复 ID、字段冲突的重复 ID。
2. 按 Day 1 规则实现冲突处理，并用注释说明为什么这样处理。
3. 给金额排序函数加金额相同的订单，观察排序结果是否符合预期。
4. 调用筛选、排序和去重前后比较原始列表，确认规则要求的输入没有被修改。
5. 如果有缺失字段，决定在当前函数中报出清楚错误，还是交给后续输入校验层处理；本周不要引入复杂框架。

### 当日产出与验收

- 重复订单规则可从代码或文档看出来。
- 相同 ID 冲突、金额并列和输入列表不变都有可复现的例子。

### 学习资源

- [Python 官方教程：列表、字典和集合](https://docs.python.org/3.12/tutorial/datastructures.html)
- [Python 官方教程：循环和可迭代对象](https://docs.python.org/3.12/tutorial/controlflow.html#for-statements)

## Day 5：为集合函数补测试

### 学习目标

- 能用 pytest 写出独立、可重复的测试函数。
- 能将业务规则翻译成输入和预期输出。
- 能覆盖正常路径和重要边界，而不只检查结果数量。

### 学习内容

1. 测试文件命名：test_*.py。
2. 测试函数命名：test_*。
3. 用 assert 检查完整结果、字段和顺序。
4. 一个测试聚焦一个行为；相同结构的输入可以考虑参数化。

### 动手练习

1. 扩展 tests/test_collections.py，为筛选、金额统计、分组、排序和去重各加测试。
2. 每个函数覆盖一个正常情况和一个空输入情况。
3. 为去重覆盖完全重复和同 ID 冲突情况。
4. 为排序覆盖升序、降序和金额相同的情况。
5. 检查调用函数前后输入列表相等，证明函数没有意外修改它。
6. 运行 uv run pytest，根据失败信息修复实现或测试预期，并记录原因。

### 当日产出与验收

- 五个集合函数至少各有正常和边界测试。
- 测试验证业务规则，而不只是验证函数“没有报错”。

### 学习资源

- [pytest 入门：编写和运行第一个测试](https://docs.pytest.org/en/stable/getting-started.html)
- [pytest 文档总目录](https://docs.pytest.org/en/stable/contents.html)

## Day 6：从 JSON 文件读取订单并生成报告

### 学习目标

- 能使用标准库 json 读写嵌套列表和字典。
- 能使用 pathlib.Path 表达文件路径。
- 能把数据、业务函数和演示入口分开。

### 学习内容

1. json.load() / json.dump() 与 json.loads() / json.dumps() 的区别。
2. UTF-8 编码和文件打开模式。
3. Path、read_text() 和 write_text() 的基本用法。
4. 文件不存在、JSON 格式错误和 JSON 顶层类型不正确时的异常处理。
5. if __name__ == "__main__" 的作用。

### 动手练习

1. 新建 data/orders.json，把样例订单保存为合法 JSON，金额字段使用整数分。
2. 写一个接收路径参数的读取函数；业务函数不要在模块导入时自动读取文件。
3. 检查读到的数据是订单列表，并确认每条记录有必需字段。
4. 组合集合函数生成报告：订单数、已支付数、销售额、客户分组、金额排序和去重数量。
5. 把命令行演示整理到 main()，保持集合函数可被测试导入；如果另建入口，就同步更新 README 中的运行命令。
6. 手动制造文件不存在和 JSON 格式错误两种情况，返回清楚、可理解的错误提示。

### 当日产出与验收

- 从项目根目录运行程序，可以读取 data/orders.json 并生成报告。
- 文件错误能清楚报出，不会打印难以理解的长堆栈作为唯一提示。

### 学习资源

- [Python 官方教程：文件读写和 JSON](https://docs.python.org/3.12/tutorial/inputoutput.html#saving-structured-data-with-json)
- [Python 标准库：json](https://docs.python.org/3.12/library/json.html)
- [Python 标准库：pathlib](https://docs.python.org/3.12/library/pathlib.html)
- [Python 官方教程：异常处理](https://docs.python.org/3.12/tutorial/errors.html)
- [Python 官方教程：模块](https://docs.python.org/3.12/tutorial/modules.html)
- [uv 项目指南：管理依赖和运行命令](https://docs.astral.sh/uv/guides/projects/)

## Day 7：端到端验收与复盘

### 学习目标

- 能从数据文件开始，说明数据如何经过函数并变成报告。
- 能解释本周代码中集合、类型、文件读写和测试的作用。
- 能发现并记录当前实现的限制。

### 动手练习

1. 从项目根目录运行 README 中记录的命令；如果保留当前入口，应能运行 uv run python -m python_agent_lab.basics.collections。
2. 运行 uv run pytest，确认测试结果与当前业务规则一致。
3. 手动修改 JSON：增加订单、改状态、加入重复 ID，再检查报告。
4. 对照规则逐项验收金额、去重、排序和空数据行为。
5. 完善根目录 README：项目目标、环境要求、运行命令、样例说明、测试命令和已知限制。
6. 不看文档，口头讲解五个函数的输入、输出和一个边界情况。
7. 写下三个仍不确定的问题，为第二周的 Python 工程基础做准备。

### 当日产出与验收

- 程序能从文件读取订单、生成报告，并通过测试。
- README 里的命令能让自己或同事知道如何运行和检查项目。
- 能用自己的话解释列表推导式、生成器表达式、字典分组、集合去重和类型标注。

### 学习资源

- [Python 3.12 官方教程总目录](https://docs.python.org/3.12/tutorial/index.html)
- [pytest 入门](https://docs.pytest.org/en/stable/getting-started.html)
- [uv 项目指南](https://docs.astral.sh/uv/guides/projects/)

## 本周业务规则记录

开始 Day 2 前填写，后续代码和测试都应遵守这些规则：

- 销售额统计口径：
- 相同订单 ID 的处理规则：
- 空订单列表时的返回结果：
- 金额相同时的排序规则：
- 缺少必需字段时的处理规则：

## 本周总结

- 本周最重要的三个概念：
- 我遇到的一个错误及原因：
- 我能独立解释的代码：
- 我还不确定的问题：
- 下周需要复习的内容：
