# 第04章　函数、作用域、闭包与装饰器

[上一章](03-collections.md) · [全书目录](README.md) · [下一章](05-iteration-resources.md)

## 1. 学习目标与前置知识

能设计签名、解释名称解析并编写行为透明的包装。前置：第1–3章。

## 2. 基础知识讲解

函数对象可以保存、传递和返回。参数按签名绑定，函数默认返回 None。普通参数、仅位置参数 `/`、仅关键字参数 `*`、可变参数与解包各有用途，不应用 **kwargs 掩盖全部接口约束。

默认参数在执行定义时求值；函数体中赋值通常建立局部绑定。global/nonlocal 指定绑定目标，并不提供线程安全。闭包让内部函数访问外部绑定，注意循环晚绑定和可变状态共享。

装饰器在定义阶段包装对象，实际函数调用发生在之后。wraps 保留常用元信息；包装仍需正确传递参数、返回值和异常。partial、lambda 和命名函数按可读性及复用需要选择。

## 3. 原理讲解与推导

把定义时与调用时分开画时间线，把名称查找与对象复制分开解释。理解装饰器表达式求值与包装顺序，再用记录事件证明。

### 7. 默认参数为什么会累积：定义与调用不是同一时刻

【语言语义】执行 def 时创建函数对象并求默认参数表达式；调用时复用这些默认对象。参数局部名称绑定到传入对象，既不是自动深复制，也不是调用方变量名称的别名。

```python
# experiment: E07
def accumulate(value, result=[]):
    result.append(value)
    return result
first = accumulate(1)
second = accumulate(2)
assert first is second and first == [1, 2]
assert accumulate.__defaults__[0] is first
def change(items):
    items.append(3)
    items = []
    return items
original = [1]
assert change(original) == []
assert original == [1, 3]
```

修复通常用 None 默认值并在函数体内创建容器，但若 None 本身是有效业务参数，应考虑独立哨兵对象。`x = x or []` 会把调用方传入的空列表换掉，未必符合接口约定。

补充机制：调用时先按签名绑定参数；`/` 限制仅位置参数，`*` 限制其后参数按名称传入。*args/**kwargs 收集的是参数，不是自动校验所有业务字段。

迁移问题：配置对象作为默认参数并在调用中修改，是否同样会共享？

### 8. 闭包为什么“全都乘 3”：绑定与查找时间

【语言语义】闭包保留访问外层绑定的能力，不是自动为循环的每一次迭代深复制值。普通自由变量在调用时查找，默认参数则在函数定义时求值。

```python
# experiment: E08
def make_wrong():
    return [lambda value: value * n for n in (1, 2, 3)]
assert [fn(10) for fn in make_wrong()] == [30, 30, 30]
def make_fixed():
    return [lambda value, n=n: value * n for n in (1, 2, 3)]
assert [fn(10) for fn in make_fixed()] == [10, 20, 30]
def counter():
    count = 0
    def next_value():
        nonlocal count
        count += 1
        return count
    return next_value
a, b = counter(), counter()
assert (a(), a(), b()) == (1, 2, 1)
```

作用域不是“执行到这一行才决定局部变量”。函数中出现赋值通常让该名称成为局部名称，读取时尚未绑定会得到 UnboundLocalError。global/nonlocal 改变绑定目标；它们不是线程安全机制。

LEGB 是常用入门模型，不能不加边界地应用到所有类体、推导式与类型注解场景。例如方法不会自动把类体名称当成自己的外层词法变量，应通过实例/类访问相应属性。

误区：默认参数绑定可以替代所有复制。绑定一个可变对象仍会共享它；工厂函数为每个闭包建立所需状态，常更清楚。

迁移问题：循环注册工具时，如何确保每个包装器调用各自的 handler？

### 9. 装饰器何时运行：定义时包装，调用时执行

【语言语义】`@decorate` 等价于在创建原函数后把它传给 decorate，再把返回对象绑定到原名称。两个装饰器由内向外包装，调用时外层先进入。

```python
# experiment: E09
from functools import wraps
events = []
def decorate(label):
    events.append("build:" + label)
    def apply(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            events.append("enter:" + label)
            try:
                return fn(*args, **kwargs)
            finally:
                events.append("exit:" + label)
        return wrapped
    return apply
@decorate("outer")
@decorate("inner")
def add(a, b):
    """加法示例。"""
    return a + b
assert events == ["build:outer", "build:inner"]
assert add(1, 2) == 3
assert events[2:] == ["enter:outer", "enter:inner", "exit:inner", "exit:outer"]
assert add.__name__ == "add" and add.__wrapped__.__name__ == "add"
```

wraps 保留常用元信息并建立 __wrapped__，不自动保证包装器的错误处理、参数校验和业务语义正确。类属性中的函数作为描述器又会参与方法绑定，这是后续对象模型主题。

误区：只在导入时打印“注册成功”就等于已执行工具；包装器只 print 忘记 return；except 后返回 None 吞掉真实失败。

应用：注册表先保存函数与 Schema，再用独立执行器负责校验、计时和异常。异步函数需要 await 其实际执行，不能只记录“创建协程对象”的耗时。

迁移问题：计时、重试两个装饰器交换顺序，会分别测到什么？

## 4. 示例与逐步走查

```python
# book-example: B04
def at_least(minimum):
    def predicate(value):
        return value >= minimum
    return predicate
small, large = at_least(10), at_least(100)
assert small(20) and not large(20)
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成默认参数、倍率闭包、调用记录装饰器；先普通注册函数再添加装饰器注册，不急着连接模型。

### L07：函数签名与默认值（P11–12）

实现 append_note(note, notes=None)，传入列表时按明确约定追加，省略时每次新建。连续两次省略 notes，结果不能共享。再写一个要求 limit 只能按名称传入的函数，说明调用错误。

验收：能区分本题“有意修改传入列表”和订单分析“不修改输入”的两个接口约定；不将所有副作用一律视为错误。

### L08：闭包与晚绑定（P13）

构造三个乘法函数，输入 10 时分别返回 10/20/30。先用循环中的 lambda 观察晚绑定，再用工厂函数或默认参数绑定修正。

再写带 nonlocal 的计数器工厂，两个工厂实例分别计数，状态不能串联。验收：解释“读自由变量的时间”和“默认参数求值时间”。

### L09：装饰器行为（P15）

实现带记录回调的同步装饰器：记录调用与完成/失败事件，保持原返回值，异常继续抛出，wraps 保留原名称与文档。

验收：加法结果相同；原函数抛 ValueError 时调用者仍收到该异常；回调中不记录敏感实参。叠加两个装饰器预测事件顺序。异步函数需要单独设计，不直接套用同步包装。

## 6. 验收与自测

**行为验收：** 多次调用状态符合约定；原函数错误不被吞掉；未知和重复注册明确失败。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

LEGB 有哪些适用边界？为什么闭包可能全得到最后一个值？装饰器交换顺序会影响什么？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](03-collections.md) · [下一章](05-iteration-resources.md)
