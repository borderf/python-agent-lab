# 原理二：函数、作用域、迭代与资源

[原理入口](README.md) · 对应 P11–20

## 7. 默认参数为什么会累积：定义与调用不是同一时刻

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

## 8. 闭包为什么“全都乘 3”：绑定与查找时间

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

## 9. 装饰器何时运行：定义时包装，调用时执行

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

## 10. for 为什么能遍历：迭代协议与生成器状态

【语言语义】for 获取迭代器并反复取下一项，以 StopIteration 结束。通常 iterable 的 __iter__ 返回 iterator；iterator 的 __iter__ 返回自己。生成器是一种保存执行位置与局部状态的迭代器。

```python
# experiment: E10
values = [1, 2]
left, right = iter(values), iter(values)
assert next(left) == 1 and next(right) == 1
def produce():
    yield 10
    return 99
g = produce()
assert iter(g) is g
assert next(g) == 10
try:
    next(g)
except StopIteration as exc:
    assert exc.value == 99
else:
    raise AssertionError("应已结束")
assert list(g) == []
```

yield 暂停执行，return 结束生成器；不要在生成器内部随意 raise StopIteration 作为结束写法。生成器表达式也有状态，不是可重复使用的惰性列表。最外层可迭代对象的求值/迭代器建立与内部逐项计算还存在时机差别，不能笼统声称创建生成器时绝不做任何工作。

应用：数据管道分清一次性流与需要重复访问的缓存；不要用两次 sum 消费同一生成器，期待相同结果。

迁移问题：一个 API 接受 Iterable 时，为什么不能默认先 len() 再遍历两次？

## 11. with 为什么能清理：退出协议与异常传播

【语言语义】上下文进入成功后，块正常结束或异常退出都会执行相应退出逻辑；退出逻辑可以选择抑制异常。进入阶段本身失败时，不能假设当前管理器的退出逻辑会代替它清理半初始化资源。

```python
# experiment: E11
events = []
class Resource:
    def __enter__(self):
        events.append("enter")
        return self
    def __exit__(self, exc_type, exc, tb):
        events.append("error" if exc_type else "normal")
        events.append("closed")
        return False
try:
    with Resource():
        raise ValueError("bad data")
except ValueError:
    pass
assert events == ["enter", "error", "closed"]
def hides_error():
    try:
        raise ValueError("lost")
    finally:
        return 1
assert hides_error() == 1
```

finally 适合清理，但在其中 return/raise 可能覆盖先前结果或错误。contextmanager 通过一次 yield 分隔进入与退出；yield 前建立资源，try/finally 保证退出处理。多资源获取可用 ExitStack，让已经获得的资源在后续获取失败时退出。

误区：所有对象成为垃圾后都立刻关闭；except Exception 能正确表达所有取消与退出；返回 True 只是表示清理成功。__exit__ 的真值还表示抑制块内异常。

迁移问题：数据库提交失败与原始业务异常同时发生，日志和异常链应怎样保留原因？

## 12. 提前 break 为什么未必释放：生成器生命周期

【语言/库约定】for 的 break 结束循环，不普遍等价于对迭代器调用 close。若还持有生成器，它的 finally 可能尚未运行。需要可确定退出时，由接口明确 close/context 管理责任。

```python
# experiment: E12
from contextlib import closing
events = []
def stream():
    events.append("opened")
    try:
        yield 1
        yield 2
    finally:
        events.append("closed")
g = stream()
assert events == []
for item in g:
    assert item == 1
    break
assert events == ["opened"]
g.close()
assert events == ["opened", "closed"]
events.clear()
with closing(stream()) as managed:
    assert next(managed) == 1
assert events == ["opened", "closed"]
```

应用：JSONL 解析和模型流式响应在正常结束、错误和客户端断开时都需关闭。不要让测试只检查完整消费时的行为，而漏掉提前停止。

迁移问题：将 `return (line for line in file)` 写在已经退出的文件 with 块后，消费时会怎样？

依据：[执行模型](https://docs.python.org/3.12/reference/executionmodel.html)、[参数定义](https://docs.python.org/3.12/tutorial/controlflow.html#defining-functions)、[迭代器](https://docs.python.org/3.12/tutorial/classes.html#iterators)、[contextlib](https://docs.python.org/3.12/library/contextlib.html)。
