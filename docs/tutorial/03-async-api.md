# 第三周：异步与 FastAPI（11–15）

[教程入口](README.md) · 起始代码：[week03_service.py](../../practice/python_ai_course/week03_service.py)

异步练习本身只需要标准库；接口练习再执行：

```powershell
uv add fastapi uvicorn
uv run python -m pytest practice/python_ai_course/checks_week03.py -q
```

HTTPX 已在第二周添加，FastAPI TestClient 会用到它。

## 第 11 课：协程、await 与并发

### 理解

调用 async def 函数得到协程对象，需要 await 或交给事件循环调度。await 在等待可等待对象时可以把执行机会交给其他任务；它不会自动让 CPU 计算变成并行。

```python
import asyncio

async def lookup(user):
    await asyncio.sleep(0.1)  # 模拟 I/O，不是实际请求
    return user

async def main():
    result = await asyncio.gather(lookup("Alice"), lookup("Bob"))
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

先顺序 await 两次，再用 gather 比较行为。gather 的结果按传入顺序组织，不按谁先完成组织；失败传播和其他任务是否停止需要单独理解，不能假设一个失败就自动完成所有清理。

### 练习

自己创建一个异步订单查询模拟器，对每个用户 await asyncio.sleep() 后返回固定整数金额。写顺序版和并发版，记录耗时并解释差异。不使用精确耗时阈值作为业务测试，因为机器负载会影响时间。

验收：能解释协程对象、任务和结果的区别；async 函数里不放 time.sleep() 或同步网络请求阻塞事件循环。

## 第 12 课：并发限制、超时与取消

### 理解

大量请求同时启动可能耗尽连接或触发限流。Semaphore 限制同时进入某段代码的任务数；并发数和每秒请求数是不同概念。

asyncio.timeout() 通过取消任务实现超时语义。CancelledError 要在清理后继续向外传播，不能捕获 BaseException 后假装成功。清理通常放在 finally。

### 练习

实现 collect_paid_totals(users, fetch_total, max_concurrency=2, timeout_seconds=1.0)：

- 按首次出现顺序对用户去重。
- 调用注入的异步 fetch_total(user)，将结果组成用户名到整数分的字典。
- 同时实际执行 fetch_total 的数量不超过 max_concurrency。
- 每个 fetch_total 从拿到并发名额开始计时；等待名额的时间不计入本课的单项超时。
- 任一任务失败或超时，取消并等待其他任务清理完，再向调用者抛原始异常。
- 空用户列表返回 {}；并发数、超时值必须合法。

提示：若采用 gather，显式保存 tasks；捕获异常后 cancel 未完成任务，再通过 gather(..., return_exceptions=True) 等待清理，最后重新抛出。TaskGroup 也是方案，但它通常包装为 ExceptionGroup；若用它，需要转换为本课约定的对外异常。

验收：记录 active 与 peak_active，确保峰值不超过限制；超时回调的 finally 确实执行；重复用户只查询一次。运行 `-k 'concurrency or timeout or async'`。检查通过后再考虑总流程时限和限速扩展。

## 第 13 课：请求模型与 FastAPI 路由

### 理解

FastAPI 路由负责把 HTTP 请求转换成业务调用，Pydantic 模型负责外部数据结构，纯业务函数负责计算。不要在路由里复制一份订单规则。

实现 create_app(orders)，注入基础样例作为只读查询来源。工厂函数返回 app，便于测试用不同数据创建应用。接口契约为：

| 接口 | 输入 | 成功结果 | 错误 |
| --- | --- | --- | --- |
| GET /health | 无 | 200，{"status":"ok"} | 无 |
| GET /reports | 可选 query user | 200，该用户或全部订单的报告 | 指定用户不存在：404 |
| POST /reports | JSON {"orders":[订单...]} | 200，提交订单的报告 | 结构/字段不合法：422；同 ID 冲突：409 |

请求模型复用第二周的 OrderModel，额外字段和错误金额类型均拒绝。GET 不修改注入数据，POST 只分析本次提交数据，不保存为全局状态。

验收：空 orders 合法，返回零统计；Bob 存在但已支付金额为 0，不能当作用户不存在。先完成 health，再接两个报告接口。

## 第 14 课：接口测试与错误边界

### 理解

TestClient 可以在进程内调用 app，无需真正监听端口。业务单元测试检查计算；接口测试进一步检查请求校验、状态码和响应结构。

```python
from fastapi.testclient import TestClient

with TestClient(create_app([])) as client:
    response = client.get("/health")
    assert response.status_code == 200
```

409 用于本课程定义的冲突，422 用于不满足请求模型的数据。不要把所有异常都转换成 200，也不要把未知内部错误都说成用户参数错误。

### 练习

先运行提供的 API 检查，再自己补：GET user=Bob、POST 空列表、POST 额外字段、请求体缺少 orders；每条写出期望状态和核心字段。

验收：接口与第一周报告输出一致；冲突返回 409，类型错误返回 422。运行 `-k api`。

## 第 15 课：集成、调试与可选持久化

### 理解

有了函数和路由，还需要解决运行与资源生命周期。异步路由不能直接执行耗时的同步 I/O；同步业务可选同步路由、线程边界或异步客户端。连接池应有明确创建与关闭位置。

### 必做练习

自己创建 `practice/python_ai_course/api.py`：从已校验文件构建 app，并导出名为 app 的变量。为简单本地演示可在明确入口加载；扩展到需要连接池时再学习 lifespan 管理资源。不要让纯计算模块导入时访问网络。

```powershell
uv run uvicorn practice.python_ai_course.api:app --reload
```

访问 /docs，实际请求 health、全部报告和 Alice 报告。README 记录启动命令与一份请求/响应。重启后重新加载源数据符合本练习的只读设计。

### 选做：SQLite

如果希望保存订单，再添加 sqlite3 存储练习：参数化 SQL、主键、事务、连接关闭和临时数据库测试。先在本地 SQLite 做通，再根据现有业务选择 MySQL/Redis 等。不要把数据库客户端更换和异步接口重构放在同一次改动中。

验收：完整第三周检查通过，服务可手动启动；能从一个失败请求定位是模型校验、订单规则还是资源调用出了问题。

参考：[asyncio 任务、取消和超时](https://docs.python.org/3.12/library/asyncio-task.html)、[同步原语](https://docs.python.org/3.12/library/asyncio-sync.html)、[FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)、[FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)。
