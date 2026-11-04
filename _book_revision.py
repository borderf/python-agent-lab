from pathlib import Path
import re

BOOK=Path(__file__).resolve().parent/'docs/python-book'
lessons={}
def lesson(n,scene,body,question,answer):
    lessons[n]=(scene.strip(),body.strip(),question.strip(),answer.strip())

lesson(1,'一笔订单需要满200元才能享受活动。你能否在运行前说出程序走哪条路径？这一章从这个可验证的问题开始，建立后面阅读所有Python代码的方法。',r'''
### 4.1 第一轮：让规则产生可见结果

先只使用整数、名称、比较与分支。金额采用整数分，200元就是20000分。规则先检查非法金额，再检查活动门槛，最后处理合法的小额订单。

```python
# study-example: S01A
amount_cents = 19900
if amount_cents < 0:
    message = "金额非法"
elif amount_cents >= 20000:
    message = "达到活动门槛"
else:
    message = "未达到活动门槛"
assert message == "未达到活动门槛"
```

从上往下读：赋值先完成，第一次比较得到False，第二次比较也得到False，于是执行else。选中分支后不会再执行其他分支。这里message最终绑定文本对象；程序没有把文本“放进整数变量”，而是让名称绑定到另一种对象。

把amount_cents改为20000，第二次比较为True；改为-1，第一次比较为True。分别验证等于门槛和刚低于门槛，比只试一个普通值更能确认边界。代码顺序本身也是规则的一部分：如果先处理所有非负金额，再写门槛判断，后者可能永远没有机会执行。

### 4.2 第二轮：看见循环中的每次状态变化

先不处理订单集合，只累计0到3，观察重复过程。range(4)提供0、1、2、3，终点4不包含在内。total在循环之前建立，每一轮读取旧值、相加，再重新绑定。

```python
# study-example: S01B
total = 0
for number in range(4):
    total = total + number
assert total == 6
assert number == 3
```

| 时刻 | number | 加法前total | 加法后total |
| --- | --- | --- | --- |
| 第1轮 | 0 | 0 | 0 |
| 第2轮 | 1 | 0 | 1 |
| 第3轮 | 2 | 1 | 3 |
| 第4轮 | 3 | 3 | 6 |

Python普通for块不创建独立的局部作用域，因此本例循环后仍可读取number。但若range为空，一轮也不执行，不能据此假定number一定获得过值。理解循环应同时考虑零次、一次和多次。

### 4.3 第三轮：搜索与穷尽是两种不同结果

for/else中的else表示循环没有因break退出。它适合搜索失败的反馈，而不是“最后一轮的if不成立”。

```python
# study-example: S01C
text = "订单A"
for character in text:
    if character == "A":
        found = True
        break
else:
    found = False
assert found is True
```

将text改为“订单B”或空字符串，循环穷尽后运行else，得到False。continue只跳过本轮剩余部分，不会像break一样跳过循环else。while也有类似退出语义，但必须保证状态推进，避免条件一直为真。

### 4.4 怎样从本章继续

本章还不要求你设计函数或异常体系。先能读懂赋值、表达式、缩进、分支和循环，并把每行执行前后的状态写出来。第二章会解释金额为什么用整数、输入文本怎样变成数据；第三章才开始把多笔记录放进容器。
''','如果range(4)改成range(0)，total和number分别怎样？能否只根据最后一行输出推断程序过程？','total仍为0；若在独立脚本中此前没有number绑定，读取它会失败。循环并不保证至少执行一次。相同最终结果也可能来自不同执行路径，应检查中间状态与边界输入。')

lesson(2,'订单页面收到的是“ 19.90 ”，统计需要1990分，报告展示19.90元，网络保存的却是字节。为什么同一金额需要不同表示？本章把这条转换链走完整。',r'''
### 4.1 先分开表示层，再做转换

输入原文、业务值和展示文本服务不同需求。原文用于定位错误，整数分用于计算，展示文本面向用户。转换时应写出单位，避免把1990分当成1990元。

```python
# study-example: S02A
amount_text = " 19.90 "
cleaned = amount_text.strip()
yuan_text, fraction_text = cleaned.split(".")
amount_cents = int(yuan_text) * 100 + int(fraction_text)
yuan, fraction = divmod(amount_cents, 100)
amount_label = f"{yuan}.{fraction:02d}"
assert amount_text == " 19.90 "
assert amount_cents == 1990
assert amount_label == "19.90"
```

这段是已知合法、恰好两位小数的走读，不是完整解析器。split得到两个片段，解包将它们分别绑定；int将数字文本转成整数，divmod再拆回商与余数。strip没有改变原文，说明字符串操作通常产生新值。

输入若是“19.9”，不能直接把9加成9分，而应按一位小数规则解释为90分；输入“19.999”在本书约定下拒绝。完整解析器要先检查字符、片段数和小数位数，再转换。第四章定义函数后再将这些步骤封装，不能让小例子承担它没有实现的输入保证。

### 4.2 精度问题应该在哪一层解决

```python
# study-example: S02B
from decimal import Decimal, ROUND_HALF_UP
assert 0.1 + 0.2 != 0.3
exact = Decimal("0.1") + Decimal("0.2")
assert exact == Decimal("0.3")
rounded = Decimal("1.005").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
assert rounded == Decimal("1.01")
```

from/import先理解为“从标准库取得需要的工具”，模块机制在第七章展开。十进制的0.1通常无法被有限二进制小数精确表示，float保存邻近值，因此误差来自表示与运算，不是print偷偷改了结果。

Decimal从文本创建可以保留十进制输入含义；从已有float创建，则接收的已经是那个近似值。quantize用于按指定指数与舍入规则产生结果。ROUND_HALF_UP是本例选择，实际业务也可能采用其他规则，尤其要约定负数、分摊余数与逐笔/汇总舍入的时机。

### 4.3 把字符串方法按任务组合起来

```python
# study-example: S02C
raw = " A-001, Alice, paid "
parts = raw.split(",")
order_id = parts[0].strip()
user = parts[1].strip()
status = parts[2].strip()
label = " | ".join((order_id, user, status))
assert label == "A-001 | Alice | paid"
assert order_id[:1] == "A" and order_id[-3:] == "001"
```

split、strip、join依次完成拆分、局部清理和重新组织。这里用到的有序容器将在第三章正式介绍，先把parts理解为一组片段。这不是通用CSV解析：字段本身含逗号或引号时，简单split会破坏结构，第七章改用csv模块。

切片右端不包含，超出范围的普通切片通常可以得到较短结果，单个越界下标却会失败。replace可以替换指定文本，startswith适合前缀判断，find返回位置或-1；不能写if text.find(...)就判断是否找到，因为位置0是假值、-1却是真值。

### 4.4 从字符走到字节

```python
# study-example: S02D
text = "采购A"
raw = text.encode("utf-8")
assert len(text) == 3 and len(raw) == 7
assert raw.decode("utf-8") == text
```

编码把Unicode文本变为字节，解码按规则把字节解释回文本。相同编码往返成立，不表示任意按字节切片仍能解码。后面读取文件与HTTP内容时，继续明确当前对象是str还是bytes。
''','为什么format_cents只负责展示，却不能修复此前用float算错的分数？怎样区分“显示两位”与“金额正确”？','格式化只把现有数值转换为文本，不会恢复已经丢失或错误解释的业务值。先在输入、计算和舍入边界保证整数分或约定的Decimal含义，再测试展示；两类正确性分别验收。')

lesson(3,'现在有多笔订单：既要保留原顺序，又要查重、分组、排序和汇总。用同一种容器硬做全部工作往往会丢失信息，本章从每个操作需要保留什么开始选择结构。',r'''
### 4.1 第一轮：列表保存顺序，字典表达记录

```python
# study-example: S03A
orders = [
    {"id": "A", "user": "Alice", "amount_cents": 1990, "status": "paid"},
    {"id": "B", "user": "Bob", "amount_cents": 1000, "status": "pending"},
    {"id": "C", "user": "Alice", "amount_cents": 10, "status": "paid"},
]
paid = []
total = 0
for order in orders:
    if order["status"] == "paid":
        paid.append(order["id"])
        total += order["amount_cents"]
assert paid == ["A", "C"] and total == 2000
```

外层列表回答“第几笔、按什么顺序”，内层字典回答“字段叫什么、值是什么”。order每轮绑定当前记录，读取字段没有复制它；paid另建列表，只追加需要的ID。若改成order["status"] = ...，则会修改原始记录，这与读取后产生新结果不同。

列表的append追加一个对象，extend逐个追加来源中的元素；insert在位置前插入，pop移除并返回某项，remove按值删除首个匹配项。删除前要明确不存在时怎样处理。遍历同一个列表时再删除其中元素会改变后续索引，常见筛选需求更适合构造新列表。

### 4.2 第二轮：用映射累积每个用户的记录

```python
# study-example: S03B
orders = [{"id":"A","user":"Alice"}, {"id":"B","user":"Bob"}, {"id":"C","user":"Alice"}]
groups = {}
for order in orders:
    user = order["user"]
    if user not in groups:
        groups[user] = []
    groups[user].append(order["id"])
assert groups == {"Alice": ["A", "C"], "Bob": ["B"]}
assert list(groups) == ["Alice", "Bob"]
```

第一轮创建Alice的桶，第二轮创建Bob的桶，第三轮复用Alice的桶。若每轮都写groups[user] = []，旧分组会被覆盖。dict.items提供键值对，keys/values提供相应视图；视图反映字典内容，不能把它当作修改时完全独立的快照。

`row[key]`适合必需字段，缺失应暴露错误；get适合确有默认语义的可选项。update合并时后来的同名值覆盖先前值；它适用于明确覆盖的配置，却不适用于尚未检查冲突的订单去重。

### 4.3 第三轮：元组与集合承担不同信息

```python
# study-example: S03C
record = ("A", 1990)
order_id, cents = record
assert order_id == "A" and cents == 1990
one = ("A",)
assert len(one) == 1
all_ids = {"A", "B", "C"}
paid_ids = {"A", "C"}
assert all_ids - paid_ids == {"B"}
assert paid_ids <= all_ids
```

元组适合位置固定的组合，逗号决定单元素元组；集合适合唯一成员和集合运算。集合丢弃重复次数，也不承诺输入顺序。若要判断订单A第二次出现时内容是否冲突，还需要保存A的首条内容，只有ID集合不够。

### 4.4 第四轮：先写清循环，再压缩表达

筛选与转换一步完成时可以使用推导式；多步更新、错误定位与冲突处理保留普通循环更容易讲清。排序前先决定按金额、按ID还是按多字段比较。

```python
# study-example: S03D
rows = [{"id":"B","amount_cents":10}, {"id":"A","amount_cents":10}, {"id":"C","amount_cents":5}]
ids = [row["id"] for row in rows if row["amount_cents"] >= 10]
assert ids == ["B", "A"]
amounts = [10, 10, 5]
assert sorted(amounts) == [5, 10, 10]
assert amounts == [10, 10, 5]
copied = amounts.copy()
result = copied.sort()
assert copied == [5, 10, 10] and result is None
```

本例先对数字排序；第四章介绍函数后再用key函数排序订单。enumerate提供位置与元素，zip按位置配对；若两个来源应严格等长，可用zip(..., strict=True)让不一致显式失败。any/all短路，空输入分别得到False/True，要结合“至少一项”和“没有反例”的含义理解。

### 4.5 第五轮：复制到底复制到哪里

```python
# study-example: S03E
original = [{"id": "A", "tags": ["new"]}]
outer_copy = original.copy()
record_copy = [dict(original[0])]
assert outer_copy is not original
assert outer_copy[0] is original[0]
assert record_copy[0] is not original[0]
assert record_copy[0]["tags"] is original[0]["tags"]
```

可以把关系画成“名称→外层列表→订单字典→tags列表”。复制外层只替换一个节点；复制字典再替换一个节点；最里面的tags仍可能共享。先指出函数会改动哪一层，再决定复制范围。这样比见到可变对象就一律deepcopy更能表达所有权。
''','一个函数声称“不修改输入”，却返回了原订单字典组成的新列表。这个接口是否已经保证调用方修改结果不会影响原输入？','没有。函数执行时不修改输入，与返回值不共享内部可变对象是两个契约。新列表仍可能引用原字典；若要求后者，应复制相应记录或返回不可变表示，并用修改结果的案例验证。')

lesson(4,'同一段订单规则将被CLI、接口与工具重复使用。函数让它变成稳定的输入输出；闭包和装饰器则让行为可以配置与扩展。本章先写普通函数，再一步步得到这些机制。',r'''
### 4.1 先得到一个能组合的返回值

```python
# study-example: S04A
def paid_total(orders):
    total = 0
    for order in orders:
        if order["status"] == "paid":
            total += order["amount_cents"]
    return total

rows = [{"status":"paid","amount_cents":1990}, {"status":"pending","amount_cents":500}]
assert paid_total(rows) == 1990
assert paid_total([]) == 0
```

执行def时建立函数，执行paid_total(rows)时才进入函数体。orders是本次调用的局部名称；return将结果交回调用处。如果把return改成print，终端虽然显示数字，调用者得到的却是None，无法可靠接入后续计算。

给函数写文档时，说明输入是否已校验、是否允许重复、是否修改输入、输出单位与失败行为。函数名不能替代这些条件；名字同为total，却可能一个统计原始行、另一个统计去重订单。

### 4.2 把签名当作小型接口

```python
# study-example: S04B
def subtotal(cents, /, *, count=1):
    return cents * count

assert subtotal(100, count=3) == 300
def collect(first, *rest, **options):
    return first, rest, options
assert collect("A", "B", "C", strict=True) == ("A", ("B", "C"), {"strict": True})
```

`/`前仅按位置，`*`后仅按关键字；*rest收集为元组，**options收集为字典。调用时的*与**执行相反方向的解包。参数形式用于表达真实意图，不要求所有函数都写成灵活但不透明的**kwargs。

### 4.3 先理解闭包，再修复晚绑定

```python
# study-example: S04C
def at_least(minimum):
    def accepts(value):
        return value >= minimum
    return accepts

small = at_least(10)
large = at_least(100)
assert small(20) is True
assert large(20) is False
```

at_least调用结束后，返回的函数仍能访问相关外层绑定。两次工厂调用建立了不同绑定，因此small与large保存不同阈值。若在同一循环里创建多个lambda，它们可能共享同一个循环变量绑定，等真正调用时才读取最后的值，这就是E08要验证的情况。

nonlocal用于修改相关外层函数的绑定，global指向定义模块中的绑定。修改一个可变对象的内容不等于重新绑定其名称，因此items.append(...)通常不需要nonlocal，`items = ...`则要按作用域规则理解。

### 4.4 不用语法糖写出第一个装饰器

```python
# study-example: S04D
from functools import wraps
events = []
def recorded(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        events.append("start")
        result = fn(*args, **kwargs)
        events.append("success")
        return result
    return wrapper

def add(left, right):
    return left + right
add = recorded(add)
assert add(2, 3) == 5
assert events == ["start", "success"]
```

recorded接收原函数，返回wrapper，再把add绑定到wrapper。以后add(...)进入包装器，包装器调用原函数，最后返回原结果。`@recorded`只是把这一变换写在定义附近；wraps保留常用元数据并提供追踪原函数的入口，不负责业务执行。

这个首版只记录成功路径。异常时第二个append不运行；第五章学完try/except/finally后，再扩展为区分成功、失败与退出的包装。先把普通调用看清，再加入错误处理，避免一次出现三层函数和四种控制流。

### 4.5 回调、lambda与partial怎样选择

```python
# study-example: S04E
from functools import partial
rows = [{"id":"B","amount_cents":10}, {"id":"A","amount_cents":10}, {"id":"C","amount_cents":5}]
ordered = sorted(rows, key=lambda row: (row["amount_cents"], row["id"]))
assert [row["id"] for row in ordered] == ["C", "A", "B"]
def multiply(value, factor):
    return value * factor
double = partial(multiply, factor=2)
assert double(7) == 14
```

key接收函数而不是它当场调用后的结果；lambda提供一个表达式，tuple键按位置逐项比较。复杂规则用具名函数说明意图。partial预先绑定部分参数，闭包则可以组织更自由的状态与行为，两者都不自动复制传入的可变配置。
''','为什么写key=get_amount与key=get_amount()含义不同？包装函数漏掉return又会怎样？','前者把函数交给排序，后者先调用函数并把其结果交给排序，常常在参数或可调用性上出错。包装器若不return原结果，成功调用仍返回None，这会改变原函数的可观察契约。')

lesson(5,'订单文件可能很大，调用方也可能只要第一条。程序不再一次获得全部结果，而是边读边处理：错误何时出现，提前停止后由谁清理？',r'''
### 4.1 用三个观察点看见惰性

```python
# study-example: S05A
events = []
def values():
    events.append("start")
    yield 10
    events.append("resume")
    yield 20

stream = values()
assert events == []
assert next(stream) == 10 and events == ["start"]
assert list(stream) == [20] and events == ["start", "resume"]
assert list(stream) == []
```

调用生成器函数先获得生成器对象，第一次推进才进入函数体。yield返回一项并暂停，局部执行状态保留，下一次从暂停点继续。list会消费到结束，消费完再list不是重新执行。这解释了为什么“接受任意Iterable”的函数不能未经说明遍历两次。

### 4.2 错误可能发生在创建之后

```python
# study-example: S05B
def parse_numbers(lines):
    for line_number, text in enumerate(lines, start=1):
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError(f"第{line_number}行不是整数") from exc
        yield value

stream = parse_numbers(["10", "bad"])
assert next(stream) == 10
try:
    next(stream)
except ValueError as exc:
    assert "第2行" in str(exc)
    assert isinstance(exc.__cause__, ValueError)
else:
    raise AssertionError("消费坏行时应失败")
```

第一条消费成功不能证明后续数据合法。try只覆盖转换动作，raise from保留底层原因并增加行号。except匹配类型及其子类，多个except通常先具体后一般；捕获Exception也不是捕获所有BaseException派生的控制事件。正常用bare raise可重新抛出当前异常，不必创建一个丢失上下文的新异常。

### 4.3 提前退出要有明确的关闭动作

```python
# study-example: S05C
from contextlib import closing
events = []
def stream_values():
    try:
        yield 1
        yield 2
    finally:
        events.append("closed")

with closing(stream_values()) as stream:
    assert next(stream) == 1
assert events == ["closed"]
```

closing在离开with时调用对象的close，使本例生成器进入finally。这里退出时没有读第二项，但清理仍发生。for中的break本身不普遍承诺关闭任意迭代器，因此资源拥有者需要明确边界，不能靠“以后垃圾回收会处理”来结束连接。

try/except负责按约定处理失败，else适合未发生异常后的正常后续，finally负责退出动作。finally中return可能覆盖原返回值或原异常，初学时避免把业务返回放在清理代码里。用contextmanager写上下文时，yield只出现一次来分隔进入和退出；自定义类的__enter__/__exit__在下一章实现。
''','为什么parse_numbers函数调用成功，但稍后next仍会失败？with中的return是否意味着不再清理？','生成器函数体按消费推进，创建成功不等于全部行已解析。进入上下文成功后，块内return也会经过退出处理；清理代码本身若改变控制流，才可能覆盖原结果，因此必须单独检查。')

lesson(6,'两个审查任务各有自己的发现列表，同时又要支持统一的长度、展示和查询操作。类在这里用于维护状态与不变量，再通过协议接入已有语言工具。',r'''
### 4.1 从两份独立状态开始

```python
# study-example: S06A
class ReviewJob:
    def __init__(self, name):
        self.name = name
        self.findings = []
    def add(self, finding):
        self.findings.append(finding)
    def __len__(self):
        return len(self.findings)
    def __repr__(self):
        return f"ReviewJob(name={self.name!r}, count={len(self)})"

a, b = ReviewJob("A"), ReviewJob("B")
a.add("缺少附件")
assert len(a) == 1 and len(b) == 0
assert a.findings is not b.findings
assert "count=1" in repr(a)
```

创建实例时初始化name与findings；调用a.add会把a绑定为self。len(a)由__len__提供语义，repr用于调试观察。若把findings=[]移到类体且不建立实例属性，两个任务可能修改同一列表；错误不是类这个工具本身造成，而是共享状态的位置不符合需求。

### 4.2 再建立受控属性与构造入口

```python
# study-example: S06B
class Limit:
    def __init__(self, value):
        if type(value) is not int or value <= 0:
            raise ValueError("limit必须是正整数")
        self._value = value
    @property
    def value(self):
        return self._value
    @classmethod
    def from_text(cls, text):
        return cls(int(text))

limit = Limit.from_text("3")
assert limit.value == 3
try:
    limit.value = 4
except AttributeError:
    pass
else:
    raise AssertionError("只读property应拒绝普通赋值")
```

classmethod接收实际类cls，因此替代构造入口能继续使用类本身的校验。property让读取仍采用属性形式，通过描述器参与访问。下划线是内部使用约定，双下划线名称改写也不是权限隔离；Python封装主要服务于接口与维护，不能用它保护不可信代码。

### 4.3 数据类减少重复，规则仍需自己写

```python
# study-example: S06C
from dataclasses import dataclass, field
@dataclass
class Report:
    job_id: str
    findings: list[str] = field(default_factory=list)

one, two = Report("A"), Report("B")
one.findings.append("missing")
assert two.findings == []
assert one == Report("A", ["missing"])
```

这里字段后的类型标注先读作字段说明，第九章学习其检查含义。dataclass可以生成初始化和相等比较，但不会自动验证每条finding符合业务。default_factory每次需要默认值时建立列表；frozen限制常规字段绑定，不会递归冻结列表。设计相等、哈希和缓存键时必须同时检查内部可变性。

### 4.4 用协议与组合代替无目的的继承

__iter__让对象可遍历，__contains__定义in的含义；需要根据ID查成员时，不必把完整字典比较语义硬套进去。__add__遇到不支持的类型可返回NotImplemented，让语言继续尝试其他运算路径；这不是抛NotImplementedError。

实例持有一个仓储或客户端，是组合；子类承诺可替换父类，是继承。多继承先看__mro__，再解释super的下一步。复杂元类、自定义__getattribute__与__slots__属于深入阅读：__slots__可限制常见实例字段并影响布局，但不自动带来不可变、线程安全或权限控制。
''','两个Report实例为什么不会共享findings？将它改为frozen后，one.findings.append还一定失败吗？','工厂在构造默认字段时分别创建列表。frozen主要限制通常的字段重新绑定，列表内部仍可变，所以append可能成功。需要不可变值时，应同时选择不可变字段表示与相应接口。')

lesson(7,'订单规则已经可以计算，但要让它读取真实文件、被其他模块复用并通过终端使用。接下来把同一个程序分清导入、读取、解析、校验和输出。',r'''
### 4.1 先跑通可控的文件往返

```python
# study-example: S07A
import json
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as folder:
    path = Path(folder) / "orders.json"
    rows = [{"id":"A", "amount_cents":1990}]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    restored = json.loads(path.read_text(encoding="utf-8"))
    assert restored == rows
    assert type(restored[0]["amount_cents"]) is int
```

TemporaryDirectory让例子不依赖个人路径，并在退出时清理。Path组合路径，write_text负责文本到文件，json.dumps负责对象到JSON文本；两个步骤不能混为“保存对象”。读取时逆向进行，解析成功后仍需业务校验。

常见模式r读取，w截断写入，a追加，x要求新建；b表示字节模式。选择w之前明确是否允许覆盖，不能把“打开输出文件”放在输入校验之前而无意清空已有报告。需要原文件不受中途失败影响时，考虑同一文件系统内的临时写入与替换，并说明持久性边界。

### 4.2 让CSV模块处理CSV结构

```python
# study-example: S07B
import csv
from io import StringIO

buffer = StringIO(newline="")
writer = csv.DictWriter(buffer, fieldnames=["user", "amount_cents"])
writer.writeheader()
writer.writerow({"user":"Alice, Inc.", "amount_cents":1990})
buffer.seek(0)
row = next(csv.DictReader(buffer))
assert row["user"] == "Alice, Inc."
assert int(row["amount_cents"]) == 1990
```

字段里有逗号，writer按格式引用，reader正确还原。读回的金额仍是文本，需要转换和校验。真实文件配合open(..., newline="", encoding="utf-8")，让csv模块处理换行约定；不要手工split逗号或重复转义。

### 4.3 入口只负责装配与反馈

```python
# study-example: S07C
import argparse
def build_parser():
    parser = argparse.ArgumentParser(description="生成订单报告")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    return parser

args = build_parser().parse_args(["orders.json", "--output", "report.json"])
assert args.input == "orders.json" and args.output == "report.json"
```

真实main取得参数，调用已有读取与计算，再输出结果；不要把核心规则只写在命令行分支里。`if __name__ == "__main__"`保护直接执行入口，import时只获得可复用定义。标准输出用于结果，标准错误用于诊断，退出码表达成功与失败。

模块是命名空间，包组织模块；python -m按包上下文运行。相对数据路径从当前工作目录解释，不自动相对源码文件。src布局项目通过安装得到可导入包，随手修改sys.path往往隐藏真实依赖。导入缓存与循环初始化再结合第三部分理解。
''','JSON能解析成字典，为什么仍可能不是有效订单？CSV读回1990为什么不必仍是int？','语法格式只决定怎样构造通用对象，不负责字段、金额、状态及权限。CSV字段通常为文本；显式转换与业务验证是格式解析之后的独立边界。')

lesson(8,'接下来订单会遇到生效日期、状态统计、最近错误和批次入库。标准库的价值在于已有抽象恰好表达需求，而不是把工具名字背下来。',r'''
### 4.1 统计、分组与相邻分组并不相同

```python
# study-example: S08A
from collections import Counter, defaultdict, deque
from itertools import groupby
states = ["paid", "pending", "paid"]
assert Counter(states) == {"paid": 2, "pending": 1}
groups = defaultdict(list)
for position, state in enumerate(states):
    groups[state].append(position)
assert groups["paid"] == [0, 2]
adjacent = [(key, list(items)) for key, items in groupby(states)]
assert adjacent == [("paid", ["paid"]), ("pending", ["pending"]), ("paid", ["paid"])]
recent = deque(maxlen=2)
recent.extend(["e1", "e2", "e3"])
assert list(recent) == ["e2", "e3"]
```

Counter保留次数，defaultdict在缺键访问时调用工厂，deque保存有界最近记录。groupby只把相邻同键元素合成一组，不自动聚合所有相同键；先排序虽可聚合，却改变全局顺序，是否允许要看需求。

### 4.2 先统一时间线，再比较有效区间

```python
# study-example: S08B
from datetime import datetime, timezone
local = datetime.fromisoformat("2026-11-04T10:00:00+08:00")
utc = datetime.fromisoformat("2026-11-04T02:00:00+00:00")
assert local == utc and local.astimezone(timezone.utc) == utc
start = datetime.fromisoformat("2026-11-01T00:00:00+00:00")
end = datetime.fromisoformat("2026-12-01T00:00:00+00:00")
assert start <= utc < end
assert not (start <= end < end)
```

左闭右开让相邻有效区间在边界不重叠。事件时刻、业务日期和持续时间分别表达；地区时区可能有夏令时，而固定偏移只是一个偏移值。经过多久用单调计时来源，发生在何时用明确时区的时钟值。

### 4.3 用一次重复主键看见事务回滚

```python
# study-example: S08C
import sqlite3
from contextlib import closing
with closing(sqlite3.connect(":memory:")) as connection:
    connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, cents INTEGER NOT NULL)")
    connection.commit()
    try:
        with connection:
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 10))
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 20))
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("重复主键应失败")
    assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
```

同一批次第一条成功、第二条失败，事务回滚第一条；closing另外负责关闭连接。占位符传值避免把引号当SQL结构，不适用于任意表名/列名。这个示例是标准库SQLite练习，后面数据库服务的连接池与迁移还需要工程层设计。

### 4.4 只取Top-K时先比较结果，再比较代价

heapq适合维护堆或从大量元素中取少量候选，排序适合完整有序结果；K接近总量时不应想当然认定堆更快。统一并列规则、输入规模、重复次数与测量环境，再用timeit/perf_counter/cProfile/tracemalloc分别观察耗时、热点和分配。

正则也按需求使用：fullmatch检查整段结构，search寻找局部，分组提取字段。匹配日期文本不等于日期真实存在。简单strip、split与startswith足够时保留简单实现；大输入和不匹配情况也应进入测试。
''','连接的with与closing为什么同时出现？数据库事务能否让随后的HTTP写入也一起回滚？','连接上下文按所选事务模式处理提交/回滚，closing负责连接资源释放。一个数据库事务不自动覆盖另一个HTTP系统；跨系统失败要在幂等和恢复章节处理。')

lesson(9,'现在同一个订单可能来自JSON、数据库、HTTP或模型。怎样既让编辑器帮助检查代码，又在运行时拒绝真实坏输入？本章把几种“类型”工具按责任分开。',r'''
### 4.1 标注先提供关系，不提供运行时保证

```python
# study-example: S09A
from typing import TypedDict, Literal
class Order(TypedDict):
    id: str
    amount_cents: int
    status: Literal["paid", "pending", "cancelled"]

def amount(order: Order) -> int:
    return order["amount_cents"]

assert amount({"id":"A", "amount_cents":10, "status":"paid"}) == 10
raw = {"id":"A", "amount_cents":"10", "status":"paid"}
assert amount(raw) == "10"  # 静态工具应提示；运行时并未自动阻止
```

最后一次调用是有意的反例。TypedDict描述字段，注解服务于读者和静态工具，Python不会因此自动验证外部字典。把Any到处传播会让静态工具放弃重要检查；object则要求先确认类型或能力才能进行特定操作。

### 4.2 Protocol把协作能力变成契约

```python
# study-example: S09B
from typing import Protocol
class Names(Protocol):
    def get(self, key: str) -> str | None: ...
class MemoryNames:
    def __init__(self):
        self.values = {"A": "Alice"}
    def get(self, key: str) -> str | None:
        return self.values.get(key)
def greet(names: Names, key: str) -> str:
    name = names.get(key)
    return "未知用户" if name is None else f"你好，{name}"
assert greet(MemoryNames(), "A") == "你好，Alice"
assert greet(MemoryNames(), "missing") == "未知用户"
```

实现无需继承Protocol，形状符合即可接受静态检查。None分支完成收窄，后面的表达式才把name当str。返回None还是抛异常属于语义，不是相同签名就自动等价；换成文件实现时用相同行为案例核验。

### 4.3 泛型保留输入与输出之间的类型关系

```python
# study-example: S09C
from typing import TypeVar
from collections.abc import Sequence
T = TypeVar("T")
def first(items: Sequence[T]) -> T | None:
    return items[0] if items else None
assert first([1, 2]) == 1
assert first(["A", "B"]) == "A"
assert first([]) is None
```

T不是“什么都不管”的Any，它把调用中的元素类型与返回类型关联。只读需求用Sequence表达，不要求一定传list；可变列表通常是不变的，因为允许把整数列表当成任意可写列表会让其他代码写入字符串。泛型先服务于真实关系，不为简单代码堆类型参数。

### 4.4 运行时边界需要真正的验证器

下面是Pydantic v2的框架示例，当前项目未安装时先阅读并在该阶段添加依赖，不将它算作标准库离线运行例子。

```python
# framework-example: F09
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
class OrderModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str = Field(min_length=1)
    amount_cents: int = Field(ge=0)
    status: Literal["paid", "pending", "cancelled"]

valid = OrderModel.model_validate({"id":"A", "amount_cents":10, "status":"paid"})
assert valid.amount_cents == 10
for bad in (True, "10", -1):
    try:
        OrderModel.model_validate({"id":"A", "amount_cents":bad, "status":"paid"})
    except ValidationError:
        pass
    else:
        raise AssertionError("入口应拒绝非法金额")
```

strict控制转换宽松程度，extra控制额外字段，Field表达约束；id只检查长度还不够，去空白后非空等业务规则仍需补入。严格模式对不同类型、Python对象与JSON入口有差异，按实际类型查转换表，而非笼统理解为“所有情况完全不转换”。
''','TypedDict、dataclass、Pydantic、Protocol能互相完全替代吗？','不能。它们分别偏向字典形状、对象样板行为、运行时校验和协作能力。根据边界选择组合；没有任何一种单独证明事实正确、授权正确或业务行为一致。')

lesson(10,'你写的去重函数输出数量正确，却悄悄改了输入。怎样让检查真正发现问题？本章从一个容易漏测的需求开始，把断言、替身、调试与回归连起来。',r'''
### 4.1 先把口头需求拆成行为

“规范化订单”至少有四件事：结果去掉两端空白，保留大小写，拒绝空ID，原输入不变。只检查结果数量，无法证明其他三项。测试期望应从需求手算，避免把实现里的同一表达式复制成答案。

下面代码保存为一个test_开头的独立文件后，用项目pytest执行；函数体为教学被测对象，测试函数才是检查。

```python
# pytest-example: T10
from copy import deepcopy
import pytest

def normalize(rows):
    result = []
    for row in rows:
        cleaned = dict(row)
        cleaned["id"] = row["id"].strip()
        if not cleaned["id"]:
            raise ValueError("id不能为空")
        result.append(cleaned)
    return result

def test_result_and_input_are_both_checked():
    raw = [{"id": " A ", "amount_cents": 10}]
    snapshot = deepcopy(raw)
    assert normalize(raw) == [{"id": "A", "amount_cents": 10}]
    assert raw == snapshot

@pytest.mark.parametrize("order_id", ["", " ", "\t"])
def test_empty_id_is_rejected(order_id):
    with pytest.raises(ValueError, match="id"):
        normalize([{"id": order_id}])
```

### 4.2 用小改动检验测试是否有辨别力

暂时把cleaned = dict(row)改成cleaned = row，测试应因输入改变而失败；恢复后再运行。再去掉空ID检查，参数化错误案例应失败。这种有目的的小故障能说明断言抓住了需求，不以测试数量或覆盖率替代实际辨别力。

fixture用于准备共享方式，tmp_path提供隔离的临时路径，monkeypatch可在正确作用域替换环境或对象。patch应针对使用处的绑定；若模块已from其他模块导入函数，只改原模块同名绑定未必影响使用处。这仍是第一章的对象绑定问题。

### 4.3 替换外部依赖，保留正在检查的规则

测试报告计算时注入固定仓储，真实金额计算继续执行；测试HTTP适配时用受控响应，真实状态检查、解析和校验继续执行。若把被测计算也mock成期望答案，测试只证明替身设置成功。

遇到失败时保留最小输入、运行命令和traceback；先定位差异发生在哪一层，再修改。日志记录关联ID与阶段，异常让调用方决定流程。最终把失败样例变成回归，调试过程才不会随着临时print删除而失去价值。

### 4.4 工具链各自回答什么

Ruff检查代码问题和格式，静态检查器分析类型关系，pytest检验行为，构建与安装检查交付，集成测试观察真实组合。通过某一项不能代替其他项。持续集成在干净环境运行约定步骤，把本地隐藏依赖暴露出来；具体命令应与项目实际配置一致。
''','若normalize只返回一条记录，长度测试通过就足够吗？把真实仓储mock掉以后，测试还证明了什么？','还需核对内容、顺序、错误与输入副作用。使用假仓储可以验证业务计算和接口契约，但没有证明真实文件/数据库连接与查询正确；后者需要相应集成检查。')

lesson(11,'分别查三个用户的数据，每次都在等待外部响应。哪些工作可以交替推进？一个失败后另外两个是否还在运行？本章用事件和任务生命周期回答，先不追求跑分。',r'''
### 4.1 先分清协程对象、调度和等待

```python
# study-example: S11A
import asyncio
async def main():
    events = []
    async def work(name):
        events.append("start:" + name)
        await asyncio.sleep(0)
        events.append("done:" + name)
        return name
    coroutine = work("A")
    assert events == []
    task = asyncio.create_task(coroutine)
    result = await task
    assert result == "A" and events == ["start:A", "done:A"]
asyncio.run(main())
```

调用async def通常先得到协程对象，create_task把它安排为任务，await等待其完成并取得结果。await另一个协程并不自动让整段业务并发；需要共同调度多个任务，且它们在合适的等待点让出控制。直接在事件循环中做阻塞I/O或长CPU计算，仍会妨碍其他任务。

### 4.2 同时执行的限制需要实际证据

```python
# study-example: S11B
import asyncio
async def main():
    gate = asyncio.Semaphore(2)
    active = peak = 0
    async def work(value):
        nonlocal active, peak
        async with gate:
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0)
                return value * 2
            finally:
                active -= 1
    results = await asyncio.gather(*(work(n) for n in range(5)))
    assert results == [0, 2, 4, 6, 8]
    assert peak <= 2 and active == 0
asyncio.run(main())
```

active/peak描述同时进入受限区域的数量，结果顺序来自gather的输入顺序，而非完成顺序。这个例子仍一次建立了所有任务；数据上百万时要用窗口或有界队列限制待处理对象。并发、每秒速率、队列容量分别控制不同资源。

### 4.3 用失败观察兄弟任务清理

```python
# study-example: S11C
import asyncio
async def main():
    started = asyncio.Event()
    events = []
    async def slow():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("cleaned")
    async def fail():
        await started.wait()
        raise ValueError("bad input")
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(slow())
            group.create_task(fail())
    except* ValueError:
        events.append("reported")
    assert events == ["cleaned", "reported"]
asyncio.run(main())
```

Event确保slow已经启动；普通子任务失败后，TaskGroup取消并等待相关兄弟任务退出，再按规则报告异常组。except*按组内匹配类型处理，不与普通except在同一try中混写。不要把这与默认gather的错误传播完全等同。

取消是协作请求，finally负责清理，清理后通常应继续传播取消。超时还要说明从排队还是获得名额开始计算；总deadline约束整个操作，不能被层层重试重置。线程中已开始的工作不会因取消等待就自动中断；进程可以隔离CPU任务，却增加启动和序列化成本，Windows入口保护也要正确。
''','peak<=2是否说明队列最多只有2项？收到父任务异常时，能否假定所有底层线程都停了？','不能。信号量约束进入区域的并发，不约束已经创建的等待任务数。任务取消、异步任务退出和底层线程停止属于不同层次，应分别用事件、协作终止及资源记录验证。')

lesson(12,'前面每章都验证了一块能力，现在要把它们组合成一个可重复运行的订单程序。一条订单怎样从输入走到报告？这一章用契约把整条链路连接起来。',r'''
### 4.1 从一条固定数据流开始

```python
# study-example: S12A
def normalize(raw):
    result = []
    for row in raw:
        cleaned = dict(row)
        cleaned["id"] = row["id"].strip()
        if not cleaned["id"] or type(row["amount_cents"]) is not int or row["amount_cents"] < 0:
            raise ValueError("非法订单")
        result.append(cleaned)
    return result

def unique(rows):
    by_id = {}
    for row in rows:
        key = row["id"]
        if key in by_id and by_id[key] != row:
            raise ValueError(f"订单冲突:{key}")
        if key not in by_id:
            by_id[key] = row
    return list(by_id.values())

def report(raw):
    rows = unique(normalize(raw))
    return {"input_count":len(raw), "unique_count":len(rows),
            "paid_amount_cents":sum(r["amount_cents"] for r in rows if r["status"] == "paid")}

raw = [{"id":" A ","amount_cents":1990,"status":"paid"},
       {"id":"A","amount_cents":1990,"status":"paid"}]
assert report(raw) == {"input_count":2,"unique_count":1,"paid_amount_cents":1990}
assert raw[0]["id"] == " A "
```

这是约定字段已存在的最小串联示例，完整项目还要检查顶层、额外字段、user、状态和错误位置。读代码时写出每层输出：先规范化两个A，再识别完全重复，最后才汇总1990；若先统计再去重，就会错误得到3980。

### 4.2 把来源和输出接到同一业务链

读取函数提供原始对象，校验层提供可计算记录，报告函数只依赖内部契约；CLI决定错误输出与退出，API决定状态码，工具执行器决定结构化结果。相同规则只保留一份实现，三个入口各自转换边界。

### 4.3 一次变更检查知识是否组合起来

新增一种状态时，先确认校验接受它，再决定是否进入paid统计，随后更新输出模型和测试。若所有改动都发生在任意入口的复制代码中，说明规则还没有集中。最后从独立环境安装并运行，证明交付不依赖个人目录。
''','为什么去重和统计交换顺序会出错？“所有函数都各自通过测试”是否足以证明组合正确？','重复记录会在去重前被多次计入。组合还需要前后条件一致，例如单位、规范化、顺序与已去重状态；单元检查之外必须验证固定数据的完整链路。')

lesson(13,'代码在你的电脑能跑，换目录或换一台机器却失败。原因往往不在业务算法，而在解释器、依赖、入口、配置和资源未成为明确输入。',r'''
### 4.1 先区分四种容易混淆的东西

pyproject描述项目与依赖要求，锁文件记录一次解析的具体选择，虚拟环境保存实际安装结果，wheel是构建产物。环境里碰巧有一个库，不表示项目声明了它；提交锁文件，也不表示数据库和配置已经准备好。应用通常需要锁定环境，作为库发布时则还要声明合理依赖范围。

本仓库已有src布局、uv_build和命令入口，先读懂实际配置再扩展。不要把教材中的示意目录直接覆盖现有项目。

```text
入口 CLI / API
    ↓ 解析配置并装配
业务服务 → 领域计算
    ↓ 依赖契约
文件 / HTTP / 数据库适配器
```

领域计算不读环境变量、不启动连接，才能在CLI、API与工具间复用。入口知道使用哪个实现，业务只知道需要什么能力。依赖注入在这里就是将协作者作为参数或构造依赖提供，不必先引入容器框架。

### 4.2 配置覆盖也应可运行地说明

```python
# study-example: S13A
def read_concurrency(cli, environment):
    raw = cli if cli is not None else environment.get("CONCURRENCY", "3")
    if isinstance(raw, bool):
        raise ValueError("不接受bool")
    text = str(raw)
    if not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise ValueError("并发必须为正整数")
    return int(text)

assert read_concurrency(None, {}) == 3
assert read_concurrency(None, {"CONCURRENCY":"4"}) == 4
assert read_concurrency(2, {"CONCURRENCY":"4"}) == 2
```

使用is not None保留显式传入值，再按契约验证，而不是用or偷偷处理0。函数接收映射，所以测试不污染真实环境；最终入口才传入实际环境。密钥来自受控配置，不硬编码进源码、演示数据或日志。

### 4.3 从安装产物验证交付

构建后在独立环境安装wheel，从非源码目录运行关键入口，核对包资源是否包含、配置缺失是否明确、错误退出是否一致。记录解释器和真实命令，再补Ruff、类型检查、pytest与构建的CI步骤。持续集成不负责替你选择正确断言，它负责在一致条件下执行这些检查。

公共函数签名、结果单位、异常类别和数据Schema属于接口，内部循环与缓存属于实现。修改接口需要考虑调用者和版本兼容；只换内部实现也要通过原有行为回归。把变更传播范围说清楚，才算理解分层。
''','锁文件存在，为什么还要从非源码目录测试wheel？','锁文件没有证明包内容正确，也没有排除当前目录对导入的帮助。独立安装与异地运行可以发现漏包、漏资源和隐含路径依赖；它仍不替代真实服务与平台检查。')

lesson(14,'调用外部订单服务，收到200却发现返回的是错误网页。网络、HTTP状态、JSON和业务数据是四道边界，本章沿一条请求依次检查。',r'''
### 4.1 看懂请求由什么组成

请求包含方法、URL、查询参数、头和可选请求体；响应包含状态、头和内容。GET通常读取资源，POST常提交数据，PUT/PATCH/DELETE有各自协议语义，但最终副作用仍由服务契约决定。Content-Type说明格式，Authorization承载认证信息，两者都不是业务数据本身。

### 4.2 用MockTransport保留真实客户端逻辑

以下需要HTTPX，安装并锁定该阶段依赖后运行；MockTransport避免真实网络，但状态检查与JSON解析真实执行。

```python
# framework-example: F14
import httpx
def handler(request):
    assert request.url.path == "/orders"
    return httpx.Response(200, json=[{"id":"A","amount_cents":10}])

with httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
    response = client.get("/orders", params={"status":"paid"})
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("订单响应必须为列表")
    assert rows[0]["amount_cents"] == 10
```

把响应分别改成500、非JSON文本和结构错误对象，观察失败分别在哪层。MockTransport不验证真实DNS、TLS、代理或服务可用性，这些要由对应集成检查补充。HTTP成功也不证明每条订单已满足领域规则。

### 4.3 为什么超时不是一个数字就够

连接、读取、写入和连接池等待可能分别受限；单次调用预算还要受整个任务deadline约束。若每层各自允许5秒并各重试三次，用户可能等远超5秒。重试前检查错误类别、动作可重复性、剩余时间与最大次数，退避和抖动只负责安排下一次时机。

客户端生命周期应覆盖适当的一组调用，以复用连接池，最后由所有者关闭。异步代码使用AsyncClient并await；不能把同步网络调用塞进async函数后便认为它不阻塞。

### 4.4 把写入超时与查询超时分开

查询失败通常不会改变远端业务状态；提交报告超时则可能发生在远端成功之后。此时先记待确认，通过稳定动作键查询或对账。重试是否安全不能只看状态码，还要看动作语义以及服务端真正提供的幂等保证。
''','MockTransport的所有测试通过后，哪些事情仍未证明？','真实网络、服务契约部署、认证配置、连接复用及生产规模行为尚未证明。离线测试主要验证客户端如何处理受控响应与错误；将证据范围说清楚。')

lesson(15,'订单能力需要提供给其他系统。接口不只是把函数放到URL后面，还需要明确数据从哪里来、身份由谁提供、错误怎样返回、连接何时关闭。',r'''
### 4.1 从路径、查询和请求体分清输入

`/orders/A`中的A常是路径参数，`?status=paid`属于查询，POST中的JSON属于请求体。路径标识资源，查询表达筛选，请求体表达结构化输入；按契约选择，不能让同一个金额在三个位置有冲突优先级。

以下是FastAPI与Pydantic v2示例；需要对应依赖。它故意只处理请求体，不把认证系统混入第一步。

```python
# framework-example: F15
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()
class Input(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    amount_cents: int = Field(ge=0)
class Output(BaseModel):
    amount_cents: int
    label: str
@app.post("/preview", response_model=Output)
def preview(body: Input):
    yuan, cents = divmod(body.amount_cents, 100)
    return {"amount_cents":body.amount_cents, "label":f"{yuan}.{cents:02d}"}
```

请求先经过结构验证，再进入函数，响应模型限制公开输出。路由负责映射，不应复制一套金额算法到每个端点。OpenAPI与/docs帮助理解接口形状，但不是业务规则、权限和错误策略的全部证明。

### 4.2 身份验证和授权是两步

身份验证回答“你是谁”，授权回答“你能对这份资源做什么”。用受信任令牌或会话解析出的tenant_id，不能让请求体任意覆盖。路径里的项目ID也需要资源授权，不是只要登录便能访问全部项目。401/403/404等反馈按一致接口约定设计，同时避免泄漏敏感资源是否存在。

CORS约束浏览器跨域访问方式，不是服务端身份验证，也不能阻止其他HTTP客户端直接请求。TLS保护传输，输入大小限制保护资源，字段验证保护数据形状，它们同样承担不同责任。

### 4.3 请求级和应用级资源分别拥有

应用lifespan适合创建与关闭共享HTTP客户端等资源，请求依赖适合提供当前身份或会话。用yield依赖表达退出清理，并验证失败路径。同步路由与异步路由的调度不同；框架不会把async路由内部任意阻塞调用自动变为非阻塞。

接口测试经过路由、验证、依赖和响应映射。先测合法1990，再测字符串、bool、负数与额外字段，再用依赖替身测试身份与租户；真实认证与数据库集成另测。需要可靠后台任务时使用持久任务机制，进程内BackgroundTasks不自动提供崩溃后恢复。
''','为什么CORS配置正确仍不能代替鉴权？共享HTTP客户端应由每个请求随意关闭吗？','CORS主要是浏览器行为约束，其他客户端仍可发请求；授权必须由服务端执行。共享资源由其应用级所有者关闭，请求退出不应破坏其他请求仍在使用的客户端。')

lesson(16,'用户点了两次提交，或者程序在写入成功后崩溃。同一动作可能再次到达，系统应产生几次业务效果？本章从具体故障窗口推导状态与幂等。',r'''
### 4.1 用稳定动作键识别重放

```python
# study-example: S16A
class MockWriter:
    def __init__(self):
        self.actions = {}
        self.effects = []
    def submit(self, key, payload):
        snapshot = dict(payload)
        if key in self.actions:
            old_payload, result = self.actions[key]
            if old_payload != snapshot:
                raise ValueError("同一动作键不能改变参数")
            return result
        result = {"report_id":len(self.effects) + 1}
        self.effects.append(snapshot)
        self.actions[key] = (snapshot, result)
        return result

writer = MockWriter()
first = writer.submit("job-A:v1", {"status":"reviewed"})
second = writer.submit("job-A:v1", {"status":"reviewed"})
assert first == second and len(writer.effects) == 1
```

这是单进程、无并发的模拟远端，不是生产级幂等存储。真实系统需要持久化、并发约束和服务端保证。例子展示关键关系：动作身份、载荷一致性和效果记录，而不是宣称加一个字典就解决分布式执行。

### 4.2 把崩溃放到正确的位置

时间线为：本地记录待执行→远端成功→本地记录成功。若在最后一步前崩溃，本地看到的是不确定，而非确定失败。恢复时用原动作键查询或重试，不能产生新键后再提交。一次数据库事务无法同时回滚外部HTTP效果。

### 4.3 审批授权的是具体版本

任务状态描述处理阶段，审批记录描述谁批准哪个载荷，执行记录描述尝试与外部效果。三个概念不要合成一个done布尔值。批准v1后载荷变成v2，应重新审核；重复恢复旧任务也要检查身份、状态和版本。

数据库唯一约束保护记录唯一性，事务保护本地多步修改；并发更新还可能需要版本号/比较后更新、锁或其他协调方式。状态转换应显式拒绝不允许的跳转，恢复先对账再决定下一步。必要时研究outbox等模式，但要先知道它缓解的是哪一段双写问题。
''','为何重试时重新生成一个UUID反而可能破坏幂等？','重复动作必须保留同一个稳定身份。每次新键让服务端把重试看作新动作，即使服务端支持幂等，也可能产生多个效果。动作键还必须绑定同一载荷与正确访问范围。')

lesson(17,'服务终于启动了，但用户仍说慢、任务偶尔消失。部署只是开始：要能知道哪里慢、什么失败、重启后怎样恢复，并用实际演练证明。',r'''
### 4.1 先画请求的时间账本

```python
# study-example: S17A
stages = {"queue_ms":30, "retrieve_ms":40, "model_ms":200, "persist_ms":10}
sequential_ms = sum(stages.values())
assert sequential_ms == 280
assert max(stages, key=stages.get) == "model_ms"
```

这些是假设的单次顺序阶段数据，不是项目实测。总延迟包含排队、外部等待、计算和写入；并行分支不能直接把耗时全部相加。平均延迟还可能掩盖尾部请求，应分别看分位数、错误率和样本窗口。

### 4.2 从现象走到证据

指标先发现某类异常增多，trace关联一次请求跨模块的阶段，日志补充受控上下文。记录request_id、job_id、阶段、耗时、错误类别和版本，避免把密钥及全文原文当作调试材料到处复制。高基数标签和日志保留也有资源成本。

### 4.3 部署进程、共享状态和任务不是同一层

镜像包含程序与运行依赖，环境配置提供部署差异，卷或外部存储承接持久数据。增加多个worker会增加进程数，每个进程自己的内存字典与连接池未必共享；不能把内存任务状态当作多实例一致数据库。

存活检查观察进程，就绪检查观察接收流量的条件。优雅关闭应停止接收新工作，按预算等待或取消在途任务并关闭资源；未完成工作由持久状态恢复。重试、熔断和降级分别缓解不同问题，降级回答也必须表达能力受限。

### 4.4 验证备份能否真正使用

在隔离环境恢复一份已知快照，核对任务、来源与结果，再演练重启和依赖不可用。RPO/RTO分别表达可接受的数据丢失范围和恢复时间目标，应按需求制定并实测。只有备份文件存在，不能说明恢复流程正确。
''','增加worker为什么可能让内存任务状态出现“有时查不到”？','各进程有独立内存，请求被分配到不同worker时可能看到不同字典。需要跨请求共享的可靠状态应进入合适的持久存储与一致性机制；不能仅靠增加并发参数解决。')

lesson(18,'模型为什么会给出流畅但没有依据的答案？理解它先预测下一个token，再生成整个回答，才能判断提示、检索、结构化输出和微调各自解决什么。',r'''
### 4.1 用最小概率例子理解生成

假设下一token只有三个候选，其概率分别为0.6、0.3、0.1。选择最大概率是一种解码，按分布采样是另一种；随后把已选token加入上下文，再预测下一项。完整回答是逐步生成的结果，不是从可信数据库提取一条已核验结论。

token由tokenizer决定，不固定等于一个汉字或一个单词。模型参数是已学习数值，推理输入是当次上下文；RAG改变上下文，微调改变参数。提示可以明确任务与格式，却不能给缺失事实提供来源。

### 4.2 先把输出校验做成可执行边界

```python
# study-example: S18A
import json
def parse_answer(text):
    payload = json.loads(text)
    if not isinstance(payload, dict) or set(payload) != {"answer", "source_ids"}:
        raise ValueError("字段不符合契约")
    if not isinstance(payload["answer"], str) or not payload["answer"].strip():
        raise ValueError("answer不能为空")
    ids = payload["source_ids"]
    if not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids):
        raise ValueError("source_ids格式错误")
    return payload

result = parse_answer('{"answer":"20%", "source_ids":["policy-a-current"]}')
assert result["source_ids"] == ["policy-a-current"]
```

它验证JSON与结构，尚未证明20%受该来源支持，也没有检查来源是否可访问。接下来分别核对身份、版本、原文与语义。模型原生结构化能力可以降低格式失败，但应用仍要处理拒绝、截断、上游错误和业务不符。

### 4.3 把Transformer公式拆成可观察步骤

先得到token向量与位置信息，再通过学习的投影形成Q/K/V；Q和K产生匹配分数，缩放后softmax变为权重，权重组合V。多头、残差、归一化和前馈层共同更新表示，因果掩码约束可见位置。B18只演示其中“分数→权重→组合”的局部，不是完整Transformer实现。

训练可用负对数概率衡量目标token被预测得多好，优化器据此调整参数。参数规模、训练数据、目标和对齐方式共同影响行为，不能从一个模型名称直接推断所有业务能力。prefill处理输入，decode逐步输出，KV cache复用计算状态；上下文越长、并发越高，资源代价也可能增加。

### 4.4 调用前先写一份提示与消息契约

提示包含任务、可信约束、非可信输入、输出格式和允许的不确定状态。少样例用于说明规则，不能与正式评测题混在一起。系统/用户/工具角色按供应商协议映射，历史压缩需要保留当前任务与证据，不能因为token不足随意删掉权限约束。

流式结果按事件累积，首token时间与完整延迟分开观察；工具参数未收完整前不执行。真实接入时记录实际模型与服务版本、上下文/输出限制、参数和可用用量。低temperature不能保证事实正确或跨环境完全复现。
''','结构正确的20%答案还需要做哪几步验证？如果没有来源，微调能否自动让它成为当前事实？','还要检查来源存在、可访问、版本有效、文本定位和是否真正支持结论。微调可能改善行为，但不自动同步当前私有事实；事实更新通常需要可信数据来源与相应检索/查询机制。')

lesson(19,'一张合同页被转成文本后，金额仍可能错一位，表格也可能丢列。模型抽取之前，先让每次转换留下定位，才能知道最终字段从哪里来。',r'''
### 4.1 用一个可回到原文的字段做起点

```python
# study-example: S19A
import re
source = {"doc_id":"contract-demo", "version":"1", "section":"费用", "text":"合同总金额为199.00元。"}
match = re.search(r"总金额为([0-9]+)\.([0-9]{2})元", source["text"])
assert match is not None
result = {
    "amount_cents":int(match.group(1))*100 + int(match.group(2)),
    "evidence":{"doc_id":source["doc_id"], "version":source["version"],
                "section":source["section"], "start":match.start(), "end":match.end(), "quote":match.group(0)},
}
evidence = result["evidence"]
assert result["amount_cents"] == 19900
assert source["text"][evidence["start"]:evidence["end"]] == evidence["quote"]
```

本例只处理约定的一种文本模式，不代表通用合同解析；它先展示字段与证据的关系。偏移量相对于这份具体文本版本，文本改变后必须重新定位。JSON/Markdown没有真实PDF页码时，不填一个假页码来凑字段。

### 4.2 上传、解析与抽取分成三个过程

上传阶段限制文件大小、格式与安全存储名，建立租户和document_id；解析阶段区分文本PDF、扫描OCR、表格和不支持内容，保存阅读顺序与定位；抽取阶段才生成候选字段，随后进行金额、日期、币种和跨字段规则检查。用户文件名不直接作为可信存储路径。

长任务采用可查询状态，失败保留阶段和原因。不能把损坏文件、无可抽取文本与确实缺字段都转换成空字符串；它们需要不同反馈。解析器版本变化时也要回归同一份材料。

### 4.3 没有值和数值为零必须区分

缺金额时value为空且needs_review为真；金额确为0时value可以是0，并保留证据。表格中的金额列错位、OCR多认一个0、模型选了另一份合同，都可能产生结构合法的字段。逐层保存中间结果，才能决定该修解析、上下文还是抽取策略。

证据原文存在不等于支持结论，还要核对合同对象、版本、条件和否定语义。模型自报置信度不自动等于校准后的正确概率，高影响字段应加入人工复核与明确规则。
''','同一份quote为什么可能在文本修改后失效？找到quote是否足以证明字段正确？','偏移与定位依赖特定文本版本，重新解析可能改变位置。quote存在只证明来源片段真实，还需验证对象、版本、上下文条件与语义支持。')

lesson(20,'用户问当前预付款上限，语料里同时有旧制度、新制度和另一租户制度。RAG首先要找到有权看且适用的证据，然后才让模型组织答案。',r'''
### 4.1 先让没有模型的检索链路跑通

```python
# study-example: S20A
from datetime import date
documents = [
    {"id":"old", "tenant":"a", "start":"2026-01-01", "end":"2026-07-01", "text":"预付款 上限 30%"},
    {"id":"current", "tenant":"a", "start":"2026-07-01", "end":"2027-01-01", "text":"预付款 上限 20%"},
    {"id":"other", "tenant":"b", "start":"2026-01-01", "end":"2027-01-01", "text":"预付款 上限 50%"},
]
as_of = date.fromisoformat("2026-11-04")
allowed = [d for d in documents if d["tenant"] == "a"
           and date.fromisoformat(d["start"]) <= as_of < date.fromisoformat(d["end"])]
terms = ["预付款", "上限"]
hits = [d for d in allowed if all(term in d["text"] for term in terms)]
assert [d["id"] for d in hits] == ["current"]
```

这是小语料关键词基线，不是通用分词检索系统。先过滤身份与有效区间，再生成候选，使旧版和其他租户不进入答案依据。若用户明确询问历史，as_of按授权的业务查询条件设置，而身份不能由模型任意改写。

### 4.2 把离线索引与在线问答分开

离线链路为文档→解析→切块→元数据→向量/倒排索引；在线链路为身份与问题→过滤→检索→必要重排→上下文→答案与引用。离线不应反复在每次问题时重建；源文档删除、更新或权限改变时，索引也必须按版本规则更新。

块要保存doc_id、version、chunk_id、来源位置、有效区间和访问范围。太短会丢适用条件，太长会稀释匹配并占上下文；重叠改善边界也会产生重复。用固定问题与证据标注比较，而不是凭块长度给出万能参数。

### 4.3 Embedding和向量库各自负责什么

Embedding把文本映射为固定维度向量，向量库保存向量及元数据并提供检索。余弦比较方向，点积还受向量长度影响，距离定义与归一化必须与模型和索引设置一致。近似最近邻用速度/内存换取一定召回权衡，不保证每次都是精确全量最优。

查询与文档向量需采用兼容模型、版本和处理方式，不能混用不同模型的同维向量。更换模型通常需要重新索引并验证。相似度不是“答案正确概率”，也不能代替版本、权威性或授权。

### 4.4 让无证据成为可接受结局

候选为空、证据冲突和证据不足分别表达，回答说明当前语料能支持什么。引用绑定实际使用的块，最终检查来源可访问且支持结论；缓存键也包含租户、权限范围、问题与知识版本等必要条件，防止把其他范围结果复用过来。
''','为什么相似度最高的旧制度不能直接回答“当前上限”？','相似度描述表示空间中的接近，不能证明时间适用性。先按可信身份和生效规则确定可见证据，再排名与生成；回答要引用实际适用版本。')

lesson(21,'向量检索漏掉制度编号，关键词检索又不擅长同义表达。混合方案可能有用，但必须用同一批题证明收益，并知道错误发生在哪一层。',r'''
### 4.1 手算再实现排名融合

```python
# study-example: S21A
def rrf(rankings, constant=60):
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, start=1):
            if item in seen:
                continue
            seen.add(item)
            scores[item] = scores.get(item, 0.0) + 1 / (constant + rank)
    return sorted(scores, key=lambda item: (-scores[item], item))

assert rrf([["A", "B"], ["B", "C"]]) == ["B", "A", "C"]
```

B在两个列表都出现，因此得到两项贡献；A与C各一项，按其名次分开。这里候选身份以字符串表示，真实系统应使用稳定chunk_id或明确的文档级身份。同一列表重复不应反复增加投票，去重策略与截取深度要在实验中固定。

### 4.2 用分母理解指标

```python
# study-example: S21B
relevant = {"A", "B"}
retrieved = ["C", "A", "D"]
recall = len(set(retrieved[:3]) & relevant) / len(relevant)
precision = len(set(retrieved[:3]) & relevant) / 3
first_rank = next((i for i, item in enumerate(retrieved, 1) if item in relevant), None)
reciprocal_rank = 0 if first_rank is None else 1 / first_rank
assert recall == 0.5 and precision == 1/3 and reciprocal_rank == 0.5
```

Recall看需要的证据找回多少，Precision看返回项中相关多少，MRR聚合多个问题的首个相关位置倒数。无相关证据题不能随意把Recall分母设为0后忽略，应另测拒答行为。分级相关性可使用带位置折扣的nDCG，先定义标注与理想排序再计算。

### 4.3 区分融合和重排

BM25等关键词信号强调词项匹配，稠密向量强调学习到的语义表示；融合整合多路候选。重排在已有候选上进一步打分，常用query与候选联合建模的模型，代价通常高于第一阶段广泛检索。根本没召回的证据，重排无法凭空补回。

比较时固定语料、过滤、题集和预算，逐题检查解析→召回→排序→生成→引用。留出未参与调参的验证题，记录质量、延迟和成本。小样本结果不能外推成普遍提升百分比，方案没有收益时保留简单基线。
''','B文档切成十个相似块后占满Top-K，文档级命中率很好，是否说明证据完整？','不一定。重复块可能掩盖其他必需证据；文档级命中、块级召回与多证据覆盖是不同口径。应固定候选身份和去重策略，并检查每题实际需要的证据集合。')

lesson(22,'模型说“我要查询供应商”，查询真的发生了吗？Agent的核心不是多写几句提示，而是把提出动作、验证、执行、反馈和停止连接成真实循环。',r'''
### 4.1 先用假模型验证最小闭环

```python
# study-example: S22A
from copy import deepcopy
calls = []
def supplier_name(arguments):
    if set(arguments) != {"supplier_id"} or arguments["supplier_id"] != "S1":
        raise ValueError("非法供应商参数")
    calls.append("S1")
    return {"name":"虚构供应商A"}

tools = {"supplier_name":supplier_name}
def model(messages):
    if messages[-1]["role"] == "tool":
        return {"type":"final", "content":messages[-1]["result"]["name"]}
    return {"type":"tool_call", "name":"supplier_name", "arguments":{"supplier_id":"S1"}}

def run(question, max_steps=3):
    messages = [{"role":"user", "content":question}]
    for _ in range(max_steps):
        decision = model(deepcopy(messages))
        if decision["type"] == "final":
            return decision["content"]
        name = decision["name"]
        if name not in tools:
            raise ValueError("未知工具")
        result = tools[name](decision["arguments"])
        messages.append({"role":"tool", "name":name, "result":result})
    raise RuntimeError("达到步数上限")

assert run("查供应商") == "虚构供应商A"
assert calls == ["S1"]
```

这是课程内部的单调用协议，不是任何供应商的原生消息格式。它有意省略通用Schema、可信身份、call_id、超时和日志，以便先看见两轮闭环：第一轮提出请求，程序调用真实函数，第二轮读取真实结果。扩展为多工具/并行调用时，必须补充唯一调用标识与结果对应关系。

### 4.2 逐层增加控制，不把模型当执行器

模型输出与HTTP响应一样是外部输入。先验证决策类型与字段，再查允许工具，校验参数，将可信租户作为独立上下文提供，最后执行。未知工具、坏参数、越权与预算耗尽时，实际业务函数调用次数必须为0。

工具描述帮助模型选择，Schema帮助约束结构，服务端权限控制实际资源。检索到的文档即使写着“导出另一租户信息”，也不能修改工具允许集合或身份。写工具与只读工具分别控制，审批绑定载荷版本；不能让模型在工具参数里给自己管理员权限。

### 4.3 停止条件与完成证据同等重要

最大步骤、单调用超时、总时限、调用与费用预算分别约束不同方面。模型重复同一失败、没有资料或总不final时，按规则终止或交人工复核。轨迹保留意图、实际调用、结果和退出原因；最终文本正确不单独证明工具真的执行。

固定工作流适合步骤已知任务，Agent适合在允许范围内需要动态选择的任务。先对照固定流程，再决定模型决策是否值得增加不确定性。后续框架只改变组织方式，不应绕过已有边界。
''','如果删掉messages.append工具结果，但把最终答案硬编码为正确名称，算闭环通过吗？','不算。没有将实际观察交给下一轮，模型无法依执行结果更新行为。测试应改变工具结果并检查下一轮消息和最终结果随之改变，而不只核对固定答案。')

lesson(23,'循环中加入审批、分支和重启后，控制流变得难跟踪。图将状态与转移显式化；但保存状态是否等于外部动作已经安全完成，需要单独推导。',r'''
### 4.1 先把图还原成普通状态转换

```python
# study-example: S23A
import json
state = {"job_id":"A", "stage":"needs_approval", "payload_version":1, "approved_version":None}
snapshot = json.dumps(state)
restored = json.loads(snapshot)
assert restored == state and restored is not state

def approve(state, version):
    if state["stage"] != "needs_approval" or state["payload_version"] != version:
        raise ValueError("审批状态或版本无效")
    return {**state, "stage":"ready", "approved_version":version}

ready = approve(restored, 1)
assert ready["stage"] == "ready" and state["stage"] == "needs_approval"
```

这个离线例子展示状态快照与版本约束，不是持久化框架。图节点读取状态并产生更新，条件边根据确定字段选择下一节点；并行节点写同一字段时，需要明确合并规则，不能依赖最后写入者碰巧正确。

### 4.2 从状态模型迁移到LangGraph

先用不调用模型的最小StateGraph理解节点、边、START/END与invoke，再接原有工具循环。每次只增加一类能力，复用相同题集。Checkpointer保存线程范围的图状态，Store保存跨线程的应用数据，二者也不同于业务订单表。

内存保存器方便演示，但进程结束数据会消失；跨进程恢复要选择实际持久后端并验证。thread_id是关联执行的键，不等于经过授权的用户身份，读取或恢复仍需资源检查。

### 4.3 中断、恢复与重放分别测试

人工审核固定候选内容与版本，再恢复同一任务。恢复可能重新执行节点中的一部分逻辑，不能把写动作随意放在会重入的位置后就认为框架保证一次执行。Checkpoint提交与远端动作成功之间仍可能有崩溃窗口，继续使用第16章的动作键与对账。

测试拒绝、过期载荷、重复resume、服务重启和写入后崩溃。图可观察、可暂停，不代表自动具备正确权限、审批与业务幂等。
''','把InMemorySaver用于演示后，为什么不能直接宣称“支持重启恢复”？','进程内内存不跨进程保存；还需要持久后端、稳定任务关联、状态兼容和真实重启检查。即使状态恢复，外部写入是否重复仍需另外验证。')

lesson(24,'同一项查供应商能力要供多个AI应用使用。MCP让交互方式有共同协议，但不会替业务服务决定谁能查哪份数据。',r'''
### 4.1 把三个层次放在一条链路上

```text
模型提出工具意图
    ↓ 应用校验与选择
Host中的Client → 协议交互 → MCP Server
                              ↓ 参数、身份与资源授权
                         原有业务函数
```

Host是组织AI应用与连接的宿主，Client是与服务交互的组件，Server提供能力。Tools用于可调用能力，Resources提供可读取上下文，Prompts提供模板等交互入口；是否支持以及怎样协商，按选择的协议版本与SDK核对。MCP不规定模型怎样思考，也不等同Agent Loop。

### 4.2 先验证适配没有改变业务语义

```python
# study-example: S24A
def local_lookup(project_id, *, tenant):
    records = {"P1":{"tenant":"a", "name":"虚构项目"}}
    item = records[project_id]
    if item["tenant"] != tenant:
        raise PermissionError("无权访问")
    return {"project_id":project_id, "name":item["name"]}

def adapter(arguments, trusted_tenant):
    if set(arguments) != {"project_id"}:
        raise ValueError("参数不符合Schema")
    return local_lookup(arguments["project_id"], tenant=trusted_tenant)

assert adapter({"project_id":"P1"}, "a")["name"] == "虚构项目"
```

这是业务适配器演示，不是MCP线协议或完整服务实现。真实Server的处理器可调用相同边界；租户来自可信会话，不来自模型可以改写的arguments。工具发现的Schema不能取代服务端验证，也不表示每个工具都应暴露给每个用户。

### 4.3 协议集成需要自己的失败检查

本地stdio与远程HTTP有不同部署、凭据及生命周期要求。按实际SDK实现发现、调用、结果转换、取消和关闭，记录所选协议与依赖版本。先让本地与协议适配器通过同一组业务案例，再增加发现失败、断连、超时和过大结果等特有检查。

SDK可能处理底层消息与协商，但应用仍负责允许集合、身份和结果用途。不要把旧版本示例字段与新协议混搭，也不要把普通JSON字典示例说成完整MCP实现。
''','MCP服务能列出一个工具，是否表示当前用户可以执行它？','发现能力与执行授权不同。宿主决定暴露范围，服务端在可信身份下验证具体资源与动作，工具参数也不能覆写该身份。')

lesson(25,'合同、供应商和制度审查可能独立进行。把它们并行就一定更好吗？先拆清输入输出与失败合并，再用同题集比较质量、成本和延迟。',r'''
### 4.1 先实现可控的并行组织器

```python
# study-example: S25A
import asyncio
async def main():
    async def contract():
        await asyncio.sleep(0)
        return {"expert":"contract", "findings":["缺条款"], "evidence_ids":["C1"]}
    async def supplier():
        await asyncio.sleep(0)
        raise TimeoutError("供应商查询失败")
    values = await asyncio.gather(contract(), supplier(), return_exceptions=True)
    good = [v for v in values if not isinstance(v, BaseException)]
    errors = [type(v).__name__ for v in values if isinstance(v, BaseException)]
    report = {"status":"partial" if errors else "completed", "results":good, "errors":errors}
    assert report["status"] == "partial" and report["errors"] == ["TimeoutError"]
    assert len(report["results"]) == 1
asyncio.run(main())
```

示例只有异步函数，验证并行与局部失败策略，尚未证明多Agent的决策收益。选择return_exceptions是为了保留完成结果；若需求是任一失败就整体停止，应选择相应的取消与清理策略。partial不能在最终汇总时被改写为“全部通过”。

### 4.2 分工应该改变信息组织

确定每个角色需要哪些输入、工具与权限，产出共同Schema：事实、证据、unknown、发现与失败。若三个角色都得到同样全文、同一错误资料并重复同一提示，它们不一定提供独立信息；不能简单投票提高可信度。

常见结构包括固定流水线、路由选择、并行专家、主管协调和生成-评审。先选能够表达当前依赖关系的最简单结构。下游严格依赖上游时，盲目并行无效；需要共享决策时，拆分也会增加通信与合并成本。

### 4.3 冲突要回到证据而非措辞

两个专家金额不一致，先核对来源与版本；一个说未知、另一个说合规，不应把未知当成反对票或忽略。汇总保留缺失项和冲突，必要时交复核。评审返工必须受次数、总时限和成本预算约束，避免无限讨论。

比较固定流程、单Agent、并行专家和带评审方案时，使用相同题集与尽可能一致预算。记录质量、实际调用数、延迟、token与人工复核率，保留简单方案作为回退。
''','上例证明了什么，尚未证明什么？','证明了指定组织方式能保留成功结果并表达局部失败。它没有证明真实模型专家更准确、证据更独立、成本更低，也没有实现全局时限与生产资源隔离。')

lesson(26,'一次聊天看起来很好，下一次改提示却变差。把质量分成可检查维度，并保留固定案例与版本，才能知道系统到底改善了什么。',r'''
### 4.1 指标先有分母与适用集合

```python
# study-example: S26A
cases = [
    {"kind":"answerable", "correct":True, "leak":False},
    {"kind":"answerable", "correct":False, "leak":False},
    {"kind":"no_evidence", "refused":True, "leak":False},
    {"kind":"forbidden", "refused":True, "leak":False},
]
answerable = [c for c in cases if c["kind"] == "answerable"]
accuracy = sum(c["correct"] for c in answerable) / len(answerable)
assert accuracy == 0.5 and not any(c["leak"] for c in cases)
```

这些是假设标签，示例演示计算口径而非模型实测。可回答题正确率、无证据拒答、越权泄漏与动作执行分别统计，不能用全部题的平均分掩盖某类严重失败。空集合、跳过和服务错误也需明确计数方式。

### 4.2 数据集应该能定位问题

每题保留输入、可信身份、时间、预期来源、允许动作与评分规则。固定开发集用于迭代，保留验证集观察泛化；不要把答案写进提示后再报告评测提升。记录数据、模型、提示、代码、检索与工具版本，必要时重复随机生成案例。

模型裁判可以辅助，但应与人工标注核对，注意同源模型偏好、位置与表达风格影响。统计不确定性随样本规模而变，小题集不能支持精确总体结论；关键失败优先人工复查，不只看一个综合分。

### 4.3 让攻击真的接触系统

恶意指令可能藏在检索文档、附件或工具返回中。将它实际放入非可信上下文，检查是否改变身份、调用越权工具、泄漏数据或覆盖确定性规则。只删除攻击材料，不能证明系统见到攻击后仍守住边界。

追踪记录模型与工具意图、校验、结果、证据和退出原因，避免索取不可验证的内部推理作为凭证。成本包含重试、检索、重排、模型、存储与复核；质量变化、费用与延迟在同一口径比较。发布前运行固定回归，出现退化时按版本回退。
''','答案引用真实来源，是否可以跳过事实核验？越权题失败一次能否用其他题高分抵消？','引用存在不证明它支持具体结论，还需语义与版本核对。越权与未授权动作应单独作为关键门槛观察，不让平均质量分掩盖这类失败。')

lesson(27,'现在不再按单项技术推进，而是交付一个用户能上传文档、提问并查看证据的DocPilot。每个中间产物都必须能追溯，方便定位真实错误。',r'''
### 4.1 用数据对象连接端到端链路

```python
# study-example: S27A
document = {"id":"D1", "tenant":"a", "version":"v1", "text":"预付款上限20%"}
chunk = {"id":"D1:v1:0", "document_id":document["id"], "tenant":document["tenant"],
         "version":document["version"], "text":document["text"]}
question = {"tenant":"a", "text":"预付款上限？"}
visible = [chunk] if chunk["tenant"] == question["tenant"] else []
response = {"status":"evidence_found" if visible else "no_evidence",
            "source_ids":[c["id"] for c in visible]}
assert response == {"status":"evidence_found", "source_ids":["D1:v1:0"]}
```

这段只检查来源身份如何沿数据流传递，不是完整问答实现。实际项目逐步补解析、切块、检索、生成、引用和评测，每次保留输入输出。不要一开始把向量库、模型、API与界面全部接上后，才第一次检查文本有没有解析正确。

### 4.2 按四个版本交付

v1完成导入与关键词检索，人工核对候选；v2加入证据回答与无证据状态；v3比较向量、融合和重排；v4增加接口、持久任务、观测与部署。每版都使用原题回归，记录引入新组件的理由。

### 4.3 演示从来源到答案，而不是只播成功聊天

展示一条正常请求的文档、块、候选、答案与引用；再展示无证据、旧版本和跨租户请求。最后制造一个已知解析错误，沿中间产物定位，修复后重跑。交付源码、锁文件、固定数据、建索引命令、评测导出与启动说明，未支持格式单独列出。

界面可以后加，先稳定服务与契约；异步文档处理需要可查询状态，而不是让浏览器无限等。索引是派生数据，更新与重建命令和版本映射也是交付的一部分。
''','若最终答案错了，首先应该换更大模型吗？','先沿解析、权限过滤、召回、排序、上下文和生成定位，判断证据在哪一步丢失或误用。模型变化只适合解决有证据支持的对应瓶颈，且要经过固定集对照。')

lesson(28,'采购审查同时涉及事实、规则、工具和审批。先让确定性流程完成一次审查，再逐步加入模型决策，才能知道错误来自业务还是Agent。',r'''
### 4.1 先做可复算的虚构规则

```python
# study-example: S28A
def review(facts):
    findings, missing = [], []
    if facts["quote_cents"] > facts["budget_cents"]:
        findings.append("OVER_BUDGET")
    if facts["prepayment_percent"] is None:
        missing.append("MISSING_PREPAYMENT")
    elif facts["prepayment_percent"] > facts["limit_percent"]:
        findings.append("PREPAYMENT_TOO_HIGH")
    return {"status":"needs_review" if missing else "completed", "findings":findings, "missing":missing}

result = review({"quote_cents":1100,"budget_cents":1000,"prepayment_percent":None,"limit_percent":20})
assert result == {"status":"needs_review", "findings":["OVER_BUDGET"], "missing":["MISSING_PREPAYMENT"]}
```

规则只适用于本书虚构练习。completed表示当前检查流程已完成，不表示所有风险消失或现实业务自动获批；missing与已发现问题可以同时存在。证据ID与规则版本还需要进入正式结果，使别人可核对与复算。

### 4.2 逐步替换决策，保留执行边界

先让固定流程调用事实与制度工具，再让模型选择需要查询什么。比较同一案例的规则结果与工具轨迹，模型负责组织解释，数值与权限仍由程序检查。无资料不能由模型补全为合规。

### 4.3 写入与协作最后独立验收

只读审查稳定后，加入候选报告、人工批准、幂等提交与恢复。拒绝/过期批准不写，重复恢复仍一个业务效果；再按真实需要加入图、MCP或专家分工。每次演进明确新增失败面、预算与回退方案。

面试演示至少包含正常、风险、缺资料、历史制度、越权和写入后崩溃。项目一页纸中的指标由自己的固定集与环境填入，不把教材目标写成已经取得的结果。
''','result中completed是否应该等同passed？为什么missing不能视为零风险？','流程结束与业务结论不同，completed只表示已完成约定检查。缺资料意味着无法判定，必须保留unknown/复核状态，不能将没有查到问题当成已经证明不存在问题。')

lesson(29,'面试官把默认列表题换成嵌套配置，背过的输出不再够用。原理学习的目标，是条件变化后仍能从对象、状态和边界推导结论。',r'''
### 4.1 从一个反例开始，而非背定义

```python
# study-example: S29A
def configure(options={"labels": []}):
    options["labels"].append("used")
    return options
one = configure()
two = configure()
assert one is two and one["labels"] == ["used", "used"]
```

先解释def执行时创建默认对象，两次调用绑定到同一字典，再解释内层列表修改共同可见。追问时可依次改变：显式传入新字典、只浅复制外层、返回结果后再修改、并发调用。每个变化继续画对象关系，不需要重背一份答案。

### 4.2 工程题同样沿时间线推导

超时先定义等待哪个阶段，再画远端写入与本地确认的先后；异步失败先区分错误已传播、兄弟任务已退出、线程已停止；RAG先检查来源、版本、权限与语义，再谈模型质量。语言题与系统题共享同一种推导方法。

### 4.3 用三轮追问检验理解

第一轮给准确结论，第二轮解释机制并写最小例子，第三轮改变输入、失败位置或资源限制。记录解释卡住之处，回到相应章补实验。不了解的实现细节说明版本与验证方法，避免将CPython一次观察当作全部Python保证。
''','将默认字典先copy一次，是否保证labels不再共享？','不保证。普通dict.copy是浅复制，新字典仍可能引用同一个labels列表。应按需要的所有权复制内层或构造独立状态，并用两次调用及返回后修改验证。')

lesson(30,'转行面试不只问你知道多少术语，还要判断你能否独立交付并解释取舍。将同一项目的需求、代码、实验和限制组织起来，而不是堆工具名称。',r'''
### 4.1 从约束开始设计系统

假设用户需要查询内部制度，先问文档格式、更新频率、租户与权限、是否需要写动作、质量与时限，再画最小链路。下面是设计示意，不是已部署架构。

```mermaid
flowchart LR
    U[可信身份与问题] --> A[API与输入校验]
    A --> R[可见范围内检索]
    R --> M[模型与输出校验]
    M --> E[答案和来源]
    A --> S[任务状态与关联记录]
```

固定流程能完成时先采用固定流程；需要动态选择才加入Agent；需要跨暂停恢复再评估图与持久状态。每次复杂度增加都回答：解决哪种已观察问题、增加什么代价、怎样验证、怎样回退。

### 4.2 把项目讲述压到可复查事实

先说用户与问题，再说基线失败、自己的改动、验证与代价。例如“在固定题集上比较关键词与融合检索”应附题集、口径、环境及逐题导出，不能只写“准确率大幅提高”。个人实验、方案设计与真实生产经历分别表述。

### 4.3 用演示验证材料一致

README命令、代码版本、数据与简历描述应指向同一个已完成版本。准备正常、无证据、越权和恢复案例，并接受一次新条件：新增租户、更新制度、模型不可用或批准后改载荷。能指出契约、状态、测试与部署影响，比复述架构图更能证明掌握。

Java接口、事务和服务经验可以迁移，但Python对象、协程取消与概率生成仍需要新的证据。把可迁移经验与亲手验证的新能力连接起来，形成可信的职业叙述。
''','如何回答“你这个项目能承受多少并发”？','先说明实际环境、请求形态、输入长度、依赖和测试口径，再给实测；没有测量就明确为估计并给出压测计划。并发数字脱离延迟、失败率和资源预算没有完整意义。')

def apply():
    assert set(lessons)==set(range(1,31))
    targets={1:[3,4,4,5],2:[2,1,3,5],3:[1,2,3,4,5],4:[1,2,3,5,4],
             5:[1,2,5],6:[1,2,3,5],7:[3,4,5],8:[1,2,5,4],9:[1,3,3,4],
             10:[1,2,3,5],11:[1,3,2],12:[1,2,4],13:[1,3,5],14:[1,2,4,4],
             15:[1,5,3],16:[4,6,5],17:[4,3,1,6],18:[2,6,3,5],19:[4,2,5],
             20:[5,2,3,6],21:[2,4,3],22:[3,2,4],23:[1,3,4],24:[2,4,5],
             25:[5,2,6],26:[3,2,4],27:[2,3,5],28:[2,3,4],29:[2,3,5],30:[3,2,5]}
    trim={n:{6,7} for n in range(1,11)}
    trim.update({11:{7,8,9},12:{5},13:{6},14:{6},15:{7},16:{7},17:{7},18:{8},
                 19:{6},20:{7},21:{6},22:{6},23:{6},24:{6},25:{7},26:{7},27:{6},28:{7},29:{6},30:{6}})
    for n,(scene,body,question,answer) in lessons.items():
        p=next(BOOK.glob(f'{n:02d}-*.md'));t=p.read_text(encoding='utf-8')
        assert '**本章从这里开始：**' not in t
        t=t.replace('## 2. 基础知识讲解','**本章从这里开始：** '+scene+'\n\n## 2. 基础知识讲解',1)
        old=re.search(r'## 2\. 基础知识讲解\n(.*?)(?=## 3\.)',t,re.S)
        basics=old.group(1)
        parts=re.findall(r'^### 4\.\d+ (.+?)\n(.*?)(?=^### 4\.\d+ |\Z)',body,re.M|re.S)
        assert len(parts)==len(targets[n]),(n,len(parts),targets[n])
        for index in sorted(trim[n],reverse=True):
            basics=re.sub(rf'^### 2\.{index} .*?(?=^### 2\.\d+ |\Z)','',basics,flags=re.M|re.S)
        if n==18:
            math=re.search(r'^### 2\.7 .*?(?=^### 2\.\d+ |\Z)',basics,re.M|re.S)
            assert math
            math_text=math.group(0).split('\n',1)[1].strip()
            basics=basics[:math.start()]+basics[math.end():]
            basics=basics.replace('### 2.3 Transformer怎样结合上下文','### 2.3 Transformer怎样结合上下文\n\n'+math_text,1)
        for target in sorted(set(targets[n]),reverse=True):
            section=re.search(rf'^### 2\.{target} .*?(?=^### 2\.\d+ |\Z)',basics,re.M|re.S)
            assert section,(n,target)
            addition=''
            for dest,(title,content) in zip(targets[n],parts):
                if dest==target:
                    addition+='\n\n#### 案例推进：'+title+'\n\n'+content.strip()
            basics=basics[:section.end()]+addition+'\n\n'+basics[section.end():]
        t=t[:old.start()]+'## 2. 基础知识讲解\n'+basics.rstrip()+'\n\n'+t[old.end():]
        check='### 6.1 先预测，再查看参考推导\n\n'+question+'\n\n<details>\n<summary>完成预测后查看解释</summary>\n\n'+answer+'\n\n</details>\n\n'
        t=t.replace('## 7. 面试问答与迁移',check+'## 7. 面试问答与迁移',1)
        p.write_text(t,encoding='utf-8')
    print('Reworked chapter openings, complete worked lessons and explanation-based self-checks for all 30 chapters.')

if __name__=='__main__': apply()
