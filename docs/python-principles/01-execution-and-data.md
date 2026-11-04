# 原理一：执行、对象、表达式与容器

[原理入口](README.md) · 对应 P01–10

## 1. 源码为什么能运行：语法、编译与执行分层

【CPython 观察】常规 CPython 会将源码解析并编译为代码对象，再执行其中指令。“解释型”不代表每次逐字符解释，也不代表没有编译。其他实现可以采用不同执行策略。

【语言语义】语法不合法时不能进入正常执行；合法代码仍可能在执行到某个名称或操作时出错。区分 SyntaxError、NameError 和 TypeError，有助于先判断问题在哪一层。

```python
# experiment: E01
source = "result = 1 + 2"
code = compile(source, "<own-example>", "exec")
namespace = {}
assert "result" not in namespace
exec(code, namespace)  # 这里执行的是自己写死的示例，不是外部输入
assert namespace["result"] == 3
try:
    compile("if True print(1)", "<bad-example>", "exec")
except SyntaxError:
    pass
else:
    raise AssertionError("应在语法阶段失败")
```

可选观察：对自己的函数使用 dis.dis，检查代码对象的 co_consts/co_names。优化与指令可能随版本改变，不能从一段字节码推断全部源码都按相同方式执行。

误区：把“不需要手动编译”理解成“没有编译”；把所有错误都当成语法错误。项目中先读取完整 traceback 和异常类型，再修改业务代码。

迁移问题：函数里有一个未定义名称，为什么定义函数可能成功，调用到该行才失败？

## 2. 赋值为什么会共享：名称绑定与对象图

【语言语义】`b = a` 让两个名称指向同一对象；它没有要求复制对象。函数参数也是绑定到调用时传入的对象。修改对象能被其他引用观察到，重新绑定一个名称不改变其他名称。

浅复制只新建外层容器；内部仍引用原对象。深复制递归复制适合复制的对象图，并处理重复引用等情况，但不等于任意外部资源都能有意义地复制。

```python
# experiment: E02
from copy import deepcopy
a = [{"tags": []}]
alias = a
shallow = a.copy()
deep = deepcopy(a)
assert alias is a and shallow is not a
a[0]["tags"].append("paid")
assert shallow == [{"tags": ["paid"]}]
assert deep == [{"tags": []}]
alias = []
assert a == [{"tags": ["paid"]}]
t = ([],)
try:
    t[0] += [1]
except TypeError:
    pass
else:
    raise AssertionError("tuple 的槽位不能重新赋值")
assert t == ([1],)  # 内部列表先完成了原地修改，之后写回槽位失败
```

最后的例子说明异常不保证操作前半部分没有副作用。`+=` 可能进行原地修改，也可能产生新对象，取决于类型协议。

误区：is 比较值；tuple 内部都不可变；del 名称等于立即释放对象；CPython 的 id 地址或小整数缓存可以作为业务规则。语言不保证对象不可达后马上释放资源，文件应显式管理。

应用：验证“不修改订单输入”时，对内部字典也保留合适快照。输出新列表也可能仍共享订单字典。

迁移问题：一个函数把参数重新设为 []，为什么调用者的原列表不变？如果调用 append 呢？

## 3. 条件为何返回字符串：真假值与短路

【语言语义】条件上下文将对象解释为真假；通常先询问 __bool__，没有时可用 __len__，均未定义时一般为真。and/or 做短路选择并返回操作数；not 返回 bool。

```python
# experiment: E03
events = []
def marker():
    events.append("called")
    return "fallback"
assert ("" or marker()) == "fallback"
assert ("ok" or marker()) == "ok"
assert events == ["called"]
assert (0 and marker()) == 0
assert bool("False") is True
assert isinstance(True, int) and True == 1
value = 0
assert (value or 10) == 10
assert (10 if value is None else value) == 0
```

误区：配置值 0 与未提供是同一概念；字符串“False”是假值；标成 int 就能自动排除 bool。是否允许 0 和 bool 取决于接口规则，不能只用真假值替代类型与范围校验。

迁移问题：超时为 0 表示非法，而数量为 0 表示合法时，应在哪一层分别处理？

## 4. 为什么格式化不修复浮点数：表示与计算

【数值表示】有限二进制浮点数不能精确表示大多数十进制小数。格式化仅改变显示。整数分能精确表达本题限定的最小货币单位；Decimal 使用十进制表示，但其运算也受到精度与舍入上下文限制。

```python
# experiment: E04
from decimal import Decimal
assert 0.1 + 0.2 != 0.3
assert f"{0.1 + 0.2:.2f}" == "0.30"
assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
assert Decimal(0.1) != Decimal("0.1")
assert 1999 + 1 == 2000
assert divmod(2000, 100) == (20, 0)
q, r = divmod(-7, 3)
assert (q, r) == (-3, 2)
assert -7 == q * 3 + r
```

// 的整数结果遵循向下取整，不是向零截断。金额分摊/折扣仍需定义舍入和余数分配规则；改用整数不会自动回答这些业务问题。

应用：先验证金额文本格式，再精确转分；不要 `int(float(text) * 100)`。比较测量误差可使用合理的 isclose 容差，订单金额规则则采用明确单位与精确表示。

迁移问题：100 分均分三人时，如何分配剩余 1 分并保证总额守恒？

## 5. 为什么字符数不等于字节数：Unicode 与编码

【语言/库约定】str 是 Unicode 文本，bytes 是字节序列。encode/decode 在文本与指定编码的字节之间转换。Python 的 str 长度统计码点，不保证等于人看到的字形数量；组合字符和 emoji 会带来差异。

```python
# experiment: E05
import unicodedata
text = "采购A"
raw = text.encode("utf-8")
assert len(text) == 3 and len(raw) == 7
assert raw.decode("utf-8") == text
composed = "\u00e9"
decomposed = "e\u0301"
assert len(composed) == 1 and len(decomposed) == 2
assert composed != decomposed
assert unicodedata.normalize("NFC", decomposed) == composed
try:
    raw[:1].decode("utf-8")
except UnicodeDecodeError:
    pass
else:
    raise AssertionError("截断的 UTF-8 字节不能正常解码")
```

误区：一个字固定占几个字节；用 errors='ignore' 把编码问题静默删除；按字节截断再直接解码。是否做 Unicode 规范化是业务决定，不能默默改变标识符的含义。

迁移问题：文件上传的字节大小限制，与用户名称字符长度限制，为什么需要两个检查？

## 6. 字典如何定位键：哈希、相等与顺序

【语义】可哈希对象需要在使用期间保持哈希值稳定，相等对象必须有相等哈希值；反过来，哈希值相同不意味着相等。字典可以区分发生碰撞但不相等的键。

【实现观察】常规 CPython 使用哈希表实现 dict/set，平均查找代价通常优于逐项扫描，但不是所有输入都保证 O(1)。字典插入顺序是语言保证，不是按键排序；set 不提供应依赖的原始插入顺序。

```python
# experiment: E06
class Key:
    def __init__(self, value):
        self.value = value
    def __hash__(self):
        return 1  # 故意碰撞，只用于实验
    def __eq__(self, other):
        if not isinstance(other, Key):
            return NotImplemented
        return self.value == other.value
table = {Key("A"): 10, Key("B"): 20}
assert len(table) == 2 and table[Key("A")] == 10
flags = {True: "first", 1: "second"}
assert len(flags) == 1 and flags[True] == "second"
ordered = {"B": 2, "A": 1}
ordered["B"] = 3
assert list(ordered) == ["B", "A"]
```

误区：哈希值作为跨进程持久标识；tuple 一定可哈希；键对象加入 dict 后可以随意修改影响相等/哈希的字段。覆盖 __eq__ 后应重新考虑 __hash__，不要盲目给可变值对象添加哈希。

应用：用 ID → 首条订单字典实现冲突检查，既保存首见次序，也保留可比较内容。

迁移问题：只用 seen_ids 为什么能去重，却无法知道同 ID 是否金额冲突？

依据：[执行模型](https://docs.python.org/3.12/reference/executionmodel.html)、[数据模型](https://docs.python.org/3.12/reference/datamodel.html)、[浮点数](https://docs.python.org/3.12/tutorial/floatingpoint.html)、[内置类型](https://docs.python.org/3.12/library/stdtypes.html)。
