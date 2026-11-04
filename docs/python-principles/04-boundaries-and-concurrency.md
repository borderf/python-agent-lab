# 原理四：数据边界、验证与并发执行

[原理入口](README.md) · 对应 P28–35、P41–60

## 19. 序列化为什么会丢语义：格式只表达有限类型

【库约定】JSON 表达对象、数组、字符串、数值、布尔与 null，没有 Python tuple、datetime 或 Decimal 的完整类型语义。编解码成功不保证业务对象往返仍相同，必须定义数据模型和转换规则。

```python
# experiment: E19
import json
from datetime import datetime
original = (1, 2)
restored = json.loads(json.dumps(original))
assert restored == [1, 2] and type(restored) is list
assert json.loads('{"id": 1, "id": 2}') == {"id": 2}
try:
    json.dumps(float("nan"), allow_nan=False)
except ValueError:
    pass
else:
    raise AssertionError("严格写出时拒绝非有限数")
left = datetime.fromisoformat("2026-11-04T10:00:00+08:00")
right = datetime.fromisoformat("2026-11-04T02:00:00+00:00")
assert left == right
```

Python JSON 的某些默认行为比严格互通格式宽松：例如重复对象键保留后值；默认处理非有限浮点也需注意。要求严格输入时，应选择明确的解析策略与业务校验，不能只看能否 loads。

时间字符串必须保留时区约定；naive 时间不包含足够信息来唯一确定绝对时刻。Decimal 转成字符串后也要保留字段的金额单位/币种契约；default=str 只让错误消失可能反而丢掉约束。

其他标准库的机制也要核对：itertools.groupby 按相邻键分组；heapq 维护堆关系，不是整个列表有序；正则匹配格式不等于业务合法。先写出需要的不变量，再选择工具。

迁移问题：重复键、未知字段、超长记录、无法确定时区的时间，应分别由哪个边界拒绝？

## 20. 数据库 with 为什么没关连接：事务与资源是两件事

【sqlite3 约定】连接作为上下文管理器时主要管理已有事务的提交/回滚，不负责自动关闭连接，也不意味着所有语句和所有事务配置行为相同。本例使用 Python 3.12 默认的传统事务控制；改变 autocommit/isolation_level 后要重新核对边界。

```python
# experiment: E20
import sqlite3
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, cents INTEGER)")
    try:
        with connection:
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 10))
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 20))
    except sqlite3.IntegrityError:
        pass
    assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    # with 已退出，但连接仍可使用。
finally:
    connection.close()
try:
    connection.execute("SELECT 1")
except sqlite3.ProgrammingError:
    pass
else:
    raise AssertionError("关闭后不能继续查询")
```

参数化 SQL 把值和语句结构分开，不应使用字符串拼接处理用户值。一个数据库事务也不会自动覆盖另一个 HTTP 服务的写入；跨边界副作用需单独设计幂等、对账和失败恢复。

应用：把连接生命周期、事务范围和业务操作分开写清楚。用临时数据库验证批次失败后是否真的全部回滚。

迁移问题：写入外部服务已经成功、本地记录成功状态前崩溃，单靠重试为什么可能重复操作？

## 21. 测试为什么会“绿但错”：观察范围与替身边界

【验证方法】断言只证明实际观察到的行为。例如只检查排序结果，不观察输入，会漏掉“不应修改输入”的要求。把真实规则全部 mock 掉，也会让错误实现看似通过。

```python
# experiment: E21
from copy import deepcopy
def sorts_in_place(rows):
    rows.sort(key=lambda row: row["cents"])
    return rows
rows = [{"id": "A", "cents": 20}, {"id": "B", "cents": 10}]
before = deepcopy(rows)
result = sorts_in_place(rows)
assert [row["id"] for row in result] == ["B", "A"]
assert rows != before  # 输出正确，但违反了本课程输入不变约定
def report_amount(fetch):
    return sum(row["cents"] for row in fetch())
assert report_amount(lambda: [{"cents": 7}, {"cents": 3}]) == 10
```

第二个例子替换了数据来源，仍真实执行加法；如果连 report_amount 都改成固定返回 10，就没有检验业务逻辑。集成测试还需补来源格式、超时与资源关闭。

项目管理同样有验证边界：静态检查不能证明业务事实，单元测试不能证明网络互通，源码目录能导入不能证明 wheel 正确。分别验证依赖、公共接口、构建产物与运行环境。

日志记录观察，不能代替异常或断言；覆盖率反映执行过的代码，不能保证断言充分。性能测试也先保证结果与业务约束相同，再用重复测量比较代价；sys.getsizeof 通常不递归计算整个对象图。

迁移问题：筛选函数测试只断言 len==2，返回错误的两条记录时为什么仍会通过？

## 22. async 为什么不会自动执行：协程与调度

【库约定】调用 async def 通常先产生协程对象。await 驱动该可等待计算，create_task 将协程交给事件循环作为任务调度。本例使用默认任务工厂；其他工厂可能改变何时开始执行的细节。

事件循环以协作方式推进任务：遇到实际需要等待的操作时，其他任务才有机会执行。async 函数里的长时间 CPU 循环或同步阻塞 I/O 不会因为关键字自动被移出事件循环。

```python
# experiment: E22
import asyncio
async def main():
    events = []
    ready = asyncio.Event()
    async def work():
        events.append("started")
        ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("cleaned")
    coroutine = work()
    assert events == []
    task = asyncio.create_task(coroutine)
    await ready.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert events == ["started", "cleaned"] and task.cancelled()
asyncio.run(main())
```

cancel 发出取消请求，不等于在任意机器指令处强制杀死任务。清理通常放 finally，CancelledError 在适当清理后继续传播。取消一个任务也不意味着远程请求一定没有产生业务效果。

迁移问题：await 一个没有真正挂起的协程，能否保证其他任务立刻获得执行机会？

## 23. 子任务失败后谁清理：gather 与 TaskGroup

【asyncio 约定】默认 gather 通常把首先出现的异常传播给等待者，不自动取消其他仍在运行的任务。TaskGroup 的常见失败路径会取消并等待其他任务，再以异常组报告。KeyboardInterrupt、SystemExit、取消等有特别规则，不能把所有结果一概而论。

```python
# experiment: E23
import asyncio
async def scenario(use_group):
    ready = asyncio.Event()
    events = []
    async def waiting():
        ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("cleaned")
    async def failing():
        await ready.wait()
        raise ValueError("failed")
    if use_group:
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(waiting())
                group.create_task(failing())
        except* ValueError:
            pass
        assert events == ["cleaned"]
    else:
        pending = asyncio.create_task(waiting())
        failed = asyncio.create_task(failing())
        try:
            await asyncio.gather(pending, failed)
        except ValueError:
            assert not pending.done()
        finally:
            pending.cancel()
            await asyncio.gather(pending, failed, return_exceptions=True)
        assert events == ["cleaned"]
async def main():
    await scenario(False)
    await scenario(True)
asyncio.run(main())
```

如果只观察 asyncio.run 返回之后，会混淆事件循环结束时的清理和 gather 自身行为，所以实验要在返回前检查任务状态。异常组改变对外异常形状，需要明确定义调用方怎样处理。

Semaphore 限制进入某段操作的任务数，不自动限制已创建任务总数，也不是每秒限流。超时上下文通过取消协作，HTTP 分项超时与整个任务时限并不等价；这些预算需要分别定义。

迁移问题：一百万个任务先全部 create_task 再等待 Semaphore，为什么仍可能占用大量内存？

## 24. 线程取消为什么没停止工作：执行边界与测量

【concurrent.futures 约定】尚未开始的 Future 可以尝试取消；已经运行的线程任务不能因此被强制终止。取消异步等待或线程结果等待，也不等于阻止已经开始的外部副作用。

```python
# experiment: E24
from concurrent.futures import ThreadPoolExecutor
from threading import Event
started, release = Event(), Event()
def blocking_work():
    started.set()
    release.wait()
    return 7
with ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(blocking_work)
    try:
        assert started.wait(timeout=2), "工作线程未开始"
        assert future.running()
        assert future.cancel() is False
    finally:
        release.set()
    assert future.result(timeout=2) == 7
```

【CPython 3.12 常规构建观察】GIL 会限制某些纯 Python CPU 密集线程的并行执行，但 I/O 或释放 GIL 的扩展可能不同；不能把它简化为“线程没用”或推断所有 Python 构建都相同。进程提供不同隔离/并行边界，同时引入启动、序列化与资源代价。

选择依据：任务是否等待 I/O、是否 CPU 密集、数据传输多少、外部库是否阻塞、是否能安全取消。用 perf_counter/timeit/cProfile/tracemalloc 分别观察时间、热点与分配，先检查输出正确，再记录规模和多次测量。缓存可能减少重复计算，也引入内存与失效问题。

应用：同步阻塞工具只放到受控执行边界，不承诺超时之后底层工作已终止；使用线程协作停止、外部幂等或隔离进程等合适机制。

迁移问题：一个写订单的同步接口超时，为什么不能立即无条件再调用一次？

依据：[JSON](https://docs.python.org/3.12/library/json.html)、[sqlite3](https://docs.python.org/3.12/library/sqlite3.html)、[asyncio](https://docs.python.org/3.12/library/asyncio-task.html)、[concurrent.futures](https://docs.python.org/3.12/library/concurrent.futures.html)、[性能分析](https://docs.python.org/3.12/library/profile.html)。
