# 第05章　迭代、生成器、异常与资源管理

[上一章](04-functions-scope.md) · [全书目录](README.md) · [下一章](06-object-model.md)

## 1. 学习目标与前置知识

能处理一次性数据流，并正确传播错误、关闭资源。前置：第4章。

## 2. 基础知识讲解

可迭代对象提供获得迭代器的途径；迭代器维护消费位置，next 在结束时报告 StopIteration。生成器通过 yield 暂停并保留状态，return 结束，yield from 委托子迭代过程。惰性不等于永不分配，也不保证更快。

try/except 匹配预期异常，else 在未出现异常的正常路径执行，finally 负责退出清理。raise from 保留原因；错误应携带足够位置和上下文，不应该返回假成功结果。

with 协议建立进入和退出边界，contextmanager 与 ExitStack 简化资源组合。提前 break、生成器关闭和事件取消需要分别设计；不要依赖垃圾回收的即时释放。

## 3. 原理讲解与推导

维护状态机：未开始→运行→暂停→结束/异常。资源的拥有者必须明确，调用方提前停止时也要有清理路径。

### 10. for 为什么能遍历：迭代协议与生成器状态

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

### 11. with 为什么能清理：退出协议与异常传播

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

### 12. 提前 break 为什么未必释放：生成器生命周期

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


## 4. 示例与逐步走查

```python
# book-example: B05
from contextlib import contextmanager
events = []
@contextmanager
def session():
    events.append("open")
    try:
        yield events
    finally:
        events.append("close")
with session() as trace:
    trace.append("work")
assert events == ["open", "work", "close"]
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

手写迭代器，完成 JSONL 惰性解析和多资源获取失败清理。为坏行记录真实物理行号。

### L10：异常与资源关闭（P18–20）

用小型 FakeResource 记录 enter/exit/closed，在 with 内主动抛 ValueError，验证资源关闭且原异常传播。分别使用类协议和 contextmanager 实现。

扩展：第二个资源建立失败时，第一个仍关闭；用 ExitStack 解决。验收：能解释 __exit__ 返回 True 的含义，以及 finally 中 return 为什么可能掩盖异常。

### L11：迭代器协议（P16）

实现只产生 0 到 n-1 的迭代器；空输入立即 StopIteration。再设计一个每次 iter() 返回新迭代器的可迭代集合。

验收：迭代器消费后第二次 list() 为空；可重复迭代集合两次结果相同。不要把迭代状态放在所有实例共享的类变量上。

### L12：惰性 JSONL（P17–20）

实现逐行解析器：跳过空行，对记录做订单校验，失败带 1 起始的物理行号和原因。第一行合法、第二行空、第三行坏 JSON 时，只取第一条不应提前触发第三行错误，继续消费才报第 3 行错误。

验收：不 read 全文件后再假装生成器；调用方提前停止时有明确 close/context 管理方式。正常结束和异常均关闭文件。

## 6. 验收与自测

**行为验收：** 正常结束、坏数据、提前停止均不泄漏资源；错误原因可定位；同一生成器不被误当可重复列表。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

for 的 break 会自动 close 吗？finally return 有何风险？异常链为何有助于调试？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](04-functions-scope.md) · [下一章](06-object-model.md)
