# 第11章　异步、线程进程与性能边界

[上一章](10-testing-tools.md) · [全书目录](README.md) · [下一章](12-python-capstone.md)

## 1. 学习目标与前置知识

根据等待、计算、资源与取消需求选择执行方式。前置：第4–10章。

## 2. 基础知识讲解

协程对象、Task、事件循环和线程/进程是不同概念。await 不自动变成并行；Semaphore 限制进入操作的数量，不限制已经创建任务数，也不等于每秒限流。

超时和取消是协作边界；gather 与 TaskGroup 的失败清理和异常形状不同。线程中已开始的工作未必随等待取消而停止；进程引入隔离和序列化代价，Windows 启动需要清楚的入口保护。

HTTP 客户端需要连接池、状态检查、JSON/数据校验、超时、有限重试和关闭责任。性能比较先保证结果一致，再记录时间、分配、数据规模与多次测量。

## 3. 原理讲解与推导

用状态转换、资源拥有者和清理责任解释并发。别把“请求者不再等待”混同“工作没有发生”，更不能据此无条件重试写入。

### 22. async 为什么不会自动执行：协程与调度

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

### 23. 子任务失败后谁清理：gather 与 TaskGroup

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

### 24. 线程取消为什么没停止工作：执行边界与测量

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


## 4. 示例与逐步走查

```python
# book-example: B11
import asyncio
async def main():
    gate = asyncio.Semaphore(2)
    async def work(value):
        async with gate:
            await asyncio.sleep(0)
            return value * 2
    assert await asyncio.gather(*(work(n) for n in range(4))) == [0,2,4,6]
asyncio.run(main())
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成 HTTP 分层错误、异步执行、线程取消和打包/性能实验；自行补有界队列处理。

### L21：HTTP 分层错误（P49）

用 HTTPX MockTransport 检查 GET /orders，分别返回合法列表、500、非 JSON 文本、结构错误对象，并模拟 ReadTimeout。状态检查、解析、校验依次发生。

验收：成功返回真正数据，其他情况保留可区分错误；无真实网络依赖。生产客户端与测试客户端由外部注入，连接关闭责任清楚。

### L22：有界异步执行（P48）

对多个用户执行注入的异步查询，用户去重、结果按需求组织，同时运行不超过 N。每个查询获得名额后有自己的超时；任一失败则取消并等待其他异步任务退出。

验收：用 active/peak_active 和 finally 事件证明限制与清理；空列表不调用回调；无效并发/超时拒绝。再用有界 Queue 或窗口限制待创建任务数，避免仅限并发却一次创建百万个任务。

### L23：线程与取消边界（P51）

把一组模拟阻塞 I/O 交给 ThreadPoolExecutor，工作线程返回结果，调用方汇总，避免无必要共享写入。开始执行的任务用 Event 协作终止或等待自然结束。

验收：取消尚未开始的 Future 与取消已开始的任务行为不同；不能宣称取消 await 就中断底层线程。再说明该任务是否适合异步实现，以及 CPU 密集任务的区别。

### L24：打包与优化实验（P45/P55）

将业务库构建 wheel，在独立临时环境安装并从非仓库目录导入，证明运行的是安装包而非恰好被当前目录找到的源码。临时环境不要修改现有全局解释器配置。

性能实验分别比较完整排序取前 K 和 heapq Top-K、列表与生成器处理。所有版本先得到相同结果，再记录数据规模、耗时、峰值内存、环境和多次测量。K=0、空数据和并列条件必须一致；描述结果，不编造普遍速度倍数。

## 6. 验收与自测

**行为验收：** 失败后无遗留异步任务，底层线程限制明确；超时、预算和重试可解释；不承诺不经测量的速度提升。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

asyncio 为什么会被阻塞？TaskGroup 为什么抛异常组？线程取消和底层操作终止有什么区别？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](10-testing-tools.md) · [下一章](12-python-capstone.md)
