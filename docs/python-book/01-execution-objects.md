# 第01章　认识执行过程、对象与控制流

[全书目录](README.md) · [全书目录](README.md) · [下一章](02-numbers-text.md)

## 1. 学习目标与前置知识

能区分语法、执行、名称绑定与副作用；能预测复制、短路与分支行为。前置：已有编程基础。

## 2. 基础知识讲解

Python 文件由语句和表达式组成。表达式求值产生对象，语句组织绑定、分支、循环和异常。缩进决定代码块；冒号引出复合语句主体。先会运行脚本和 `python -m`，再通过 traceback 判断错误类型、调用路径和触发位置。

名称引用对象；赋值不会默认复制。`==` 检查相等，`is` 检查身份；None 判断使用身份语义。list/dict 可变，数字和字符串不可变；tuple 固定所包含的引用，内部仍可能引用可变对象。

if/elif 依次选择分支，for 消费可迭代对象，while 重复检查条件。break 退出当前循环，continue 跳过当前轮剩余操作；循环 else 在没有 break 的情况下执行。and/or 短路且返回操作数，不能把 0 与未提供参数混为一谈。

## 3. 原理讲解与推导

先用对象图解释每个名称指向什么，再按执行顺序区分对象修改和名称重绑定。把“Python 是解释型语言”展开到源码、代码对象与执行三个层次；字节码属于实现观察。

### 1. 源码为什么能运行：语法、编译与执行分层

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

### 2. 赋值为什么会共享：名称绑定与对象图

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

### 3. 条件为何返回字符串：真假值与短路

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

## 4. 示例与逐步走查

```python
# book-example: B01
def describe(value):
    return {"type": type(value).__name__, "is_none": value is None, "truth": bool(value)}
assert describe(0) == {"type": "int", "is_none": False, "truth": False}
assert describe("False")["truth"] is True
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

先遮住 E01–E03 的断言做输出预测，再完成引用复制和参数缺省题。另写 for/else 搜索，分别覆盖找到、未找到与空列表。

### L01：引用与复制（P02）

用 `a = [{"tags": ["paid"]}]` 分别构造别名、浅复制和深复制。修改外层列表，再修改 tags，记录三个版本受到的影响。预测结果后运行，并画出名称与对象的引用关系。

验收：能解释为什么“外层不是同一个列表”不足以证明内部状态独立；不用 id 数值规律推断语义。

### L02：真假值与边界（P03）

实现 choose_limit(value, default=10)：只有 None 使用默认值；0 是合法值；负数、bool 和非整数报 ValueError。用 0/None/False/空字符串/5 分别检查。对比 `value or default` 为什么破坏 0 的语义。

扩展：用 for/else 搜索目标，只在没有找到时报告不存在；与用标志变量的版本比较。

## 6. 验收与自测

**行为验收：** 能解释每处副作用；两个基础函数已有实现时复用并补反例。不得依赖小整数缓存或固定 id 数值。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

赋值、浅复制、深复制如何选择？函数修改列表和重绑定参数有什么区别？异常是否意味着此前没有副作用？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[全书目录](README.md) · [下一章](02-numbers-text.md)
