# 第一周：Python 与订单分析（01–05）

[教程入口与统一规则](README.md) · 起始代码：[week01_orders.py](../../practice/python_ai_course/week01_orders.py)

## 第 01 课：变量、对象与条件

### 理解

Python 名称绑定到对象。`b = a` 不复制列表；名称重新赋值和修改对象是两件事。Java 的引用经验能帮助理解这里，但 Python 的列表切片、字典和推导式需要实际练习。

```python
a = ["paid"]
b = a
b.append("pending")
print(a)                 # ['paid', 'pending']
b = ["cancelled"]
print(a)                 # a 仍指向原来的列表
```

`a.copy()` 创建新的外层列表，内部可变对象仍共享。试把元素换成 `{"status": "paid"}`，修改浅复制结果的内部字典，再与 `copy.deepcopy(a)` 比较。

条件语句使用缩进与冒号。`and`、`or` 有短路行为，而且返回操作数，不一定返回 bool；`"" or "anonymous"` 得到字符串。`None`、0、空字符串和空容器在判断中是假值。

### 必做练习

1. 实现 normalize_name(value)：去掉两端空白，保留大小写；空白字符串或非字符串抛 ValueError。
2. 实现 format_cents(cents)：非负整数分转为两位小数的字符串，不带“元”；拒绝 bool、float 和负数。用 divmod() 或整数除法与余数处理。
3. 在临时脚本中分别写出引用、浅复制、深复制三个例子；解释哪种修改影响原数据。

验收输入：`" Alice " → "Alice"`；`"  " → ValueError`；`1999 → "19.99"`；`1 → "0.01"`；`0 → "0.00"`。运行 `-k 'name or format'`。

提示：`type(True) is int` 是 False，但 `isinstance(True, int)` 是 True。不要用 eval() 转换用户输入。普通注释写 #，文档字符串放在函数体第一条语句。

## 第 02 课：字符串、列表、字典与集合

### 理解

订单列表保留顺序和重复记录，订单字典保存字段，set 保存唯一 ID。把所有订单直接转 set 不可行：dict 是可变且不可哈希的对象。先提取 ID 再去重。

```python
rows = [{"id": "A", "status": "paid"}, {"id": "B", "status": "pending"}]
paid_ids = [row["id"] for row in rows if row["status"] == "paid"]
all_ids = {row["id"] for row in rows}
```

列表推导式回答“输出哪些元素、满足什么条件”，不是把任意复杂流程压成一行。需要多步状态更新时，普通 for 循环往往更清楚。

### 必做练习

1. 实现 get_paid_orders：返回已支付订单，保持输入顺序。
2. 实现 collect_ids：返回 `(全部 ID 集合, 已支付 ID 集合, 非已支付 ID 集合)`；此函数的输入已按规则去重。
3. 对基础数据分别用循环和推导式完成，说明返回的 list 和 set 各适合做什么。

验收：已支付 ID 按顺序为 10001、10003；非已支付 ID 集合为 10002、10004；空列表得到空列表或三个空集合。运行 `-k 'paid_filter or ids'`。

思考：同 ID 出现 paid 和 cancelled 时，先做集合差会掩盖冲突，所以统一规则要求先去重并检查冲突。

## 第 03 课：函数、参数、生成器与金额精度

### 理解

函数通过返回值交付结果；只 print 的函数默认返回 None。参数接收对象引用，函数里修改列表或字典会影响调用者。类型标注描述契约，不负责运行时检查。

```python
def sum_positive(values: list[int], *, minimum: int = 0) -> int:
    return sum(value for value in values if value > minimum)
```

`*` 后的参数必须按名称传入。常见参数还有默认值、`*args` 和 `**kwargs`；先会读和写普通参数与关键字参数，再按需要使用可变参数。

不要用 `def add(row, rows=[])` 保存默认列表：默认对象只创建一次。需要新容器时用 None 作为默认值，再在函数内创建。

生成器表达式逐项产出值：

```python
numbers = (n * 2 for n in [1, 2, 3])
print(sum(numbers))  # 12
print(sum(numbers))  # 0，已经消费完
```

它减少中间列表，但不保证总是更快。需要反复遍历结果时保留列表更方便。

金额练习固定使用整数分。`0.1 + 0.2 == 0.3` 是 False；`.2f` 只改变显示。外部十进制金额若必须转分，可用 Decimal 从字符串创建并明确小数位与舍入规则；不要用 `int(float(text) * 100)` 作为通用金额解析。本课程输入直接提供整数分。

### 必做练习

1. 实现 total_amount_cents(orders, status=None)：None 统计全部；指定合法状态时只统计该状态。输入已去重，返回 int。
2. 实现 group_by_user：用户名映射到该用户的订单列表，保留组内顺序。
3. 给旧 collections.py 的金额改造列出受影响位置：类型、样例、汇总、排序、展示和测试。可以先在独立练习区完成，再迁回原模块。
4. 自己写一个可变默认参数的错误示例，运行两次，再修正并解释原因。

验收：全部 129600 分；paid 79800 分；pending 39900 分；cancelled 9900 分；空输入 0。Alice 分组顺序为 10001、10003。运行 `-k 'money or group'`。

## 第 04 课：去重、排序与业务规则

### 理解

只记 seen_ids 可以判断“见过没有”，不能比较“内容相同还是冲突”。需要比较首条记录时，可以维护 `ID → 首条订单` 的字典。数据结构由需求决定。

`sorted(rows, key=..., reverse=...)` 返回新列表；`rows.sort()` 原地修改并返回 None。Python 排序稳定：金额相同时，升序和降序都保持相同键记录原先的相对顺序。

### 必做练习

1. 实现 deduplicate_orders：完全重复只留首条；同 ID 字段冲突抛 ValueError，错误文字包含该 ID。保持首见顺序。
2. 实现 sort_orders：按 amount_cents 排序，reverse 默认 False。
3. 使用 data 中 duplicate_orders、conflicting_orders、tied_orders 三份数据，先手算再运行。
4. 用 deepcopy 保存输入快照，检查调用前后相等；新列表不代表内部订单也被深复制。

验收：重复样例 5 条变 4 条；冲突样例报错且包含 10001；并列样例升序 C、A、B，降序 A、B、C；输入完全不变。运行 `-k 'duplicate or conflict or sort or unchanged'`。

扩展：比较保留首条、保留末条、冲突报错三种策略各适合什么业务。课程检查采用统一的冲突报错策略。

## 第 05 课：JSON、文件、异常与组合

### 理解

JSON 是文本格式；解析 JSON 只能证明语法合法，不能证明内容符合订单结构。`TypedDict` 也不会替你做运行时校验。

```python
import json
from pathlib import Path

raw = json.loads(Path("input.json").read_text(encoding="utf-8"))
```

`json.load(file)` 接收打开的文件，`json.loads(text)` 接收字符串。`dump`/`dumps` 则输出文件/字符串。文件路径相对于当前工作目录，不能假设永远是脚本目录。

### 必做练习

1. 实现 validate_orders(raw)：按教程入口的规则检查顶层、字段、类型、状态；返回规范化的新订单字典，不修改 raw。失败抛 ValueError，尽量说明第几条、哪个字段。
2. 实现 load_orders(path)：读 UTF-8 JSON 并调用校验；FileNotFoundError 和 JSONDecodeError 保持可识别，不统一伪装为空列表。
3. 实现 build_report：先去重再汇总，输出入口文档规定的六个字段。用户汇总包含所有用户，没有已支付订单的用户金额为 0。
4. 自己创建 `practice/python_ai_course/cli.py`，用 main() 把读取、报告和展示串起来。捕获预期错误并打印清楚说明；模块导入时不执行流程。

验收：基础数据和重复数据报告金额一致、input_count 不同；空输入输出零统计和空用户字典；缺字段、金额为 True、字符串金额、未知状态均报错。运行完整 checks_week01.py。

阶段交付：一条命令从 JSON 生成报告，能够解释文件错误、格式错误和业务数据错误分别发生在哪一步。

参考：[数据结构](https://docs.python.org/3.12/tutorial/datastructures.html)、[函数与参数](https://docs.python.org/3.12/tutorial/controlflow.html#defining-functions)、[文件与 JSON](https://docs.python.org/3.12/tutorial/inputoutput.html)、[浮点数](https://docs.python.org/3.12/tutorial/floatingpoint.html)。
