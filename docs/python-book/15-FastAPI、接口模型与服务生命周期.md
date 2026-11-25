# 第15章　FastAPI、接口模型与服务生命周期

[上一章](14-外部数据模型、HTTP与可靠调用.md) · [全书目录](教材目录.md) · [下一章](16-数据库、任务状态、幂等与审批.md)

## 1. 学习目标与前置知识

前置：第12–14章。要把已有订单函数封装成可测试接口，而不是在路由里再写一套业务规则。

**任务卡**
- 接收：第12章 `build_report`、第14章 `fetch_orders` 及其错误类型。
- 只新增：FastAPI 请求/响应模型、依赖注入、应用 lifespan 和接口测试。
- 交付：`order_service/main.py` 与 `tests/test_api.py`，提供 `/reports` 和 `/external-report`。
- 验收：200/422/409/502 路径可区分，形状非法不调用业务，空白字符串形状合法但由业务拒绝并返回422，应用退出后共享 HTTP 客户端关闭。

**本章从这里开始：** 同一份订单规则现在要供其他系统调用。接口多了一层输入、身份、错误和资源责任；路由只做协议转换，业务仍留在原函数。

## 2. 基础知识讲解

### 2.1 请求模型与响应模型约束不同边界

请求模型拒绝缺字段、错误类型、负数、额外字段和非法状态；响应模型只公开约定结构。验证失败发生在业务调用前，业务冲突不应被改写成 422 或空结果。

路径参数标识资源，查询参数表达筛选，JSON 请求体表达结构化输入。不要在多处放同一个金额并依赖隐含优先级。

FastAPI 中写在路径模板里的参数来自 path；未嵌入路径的函数标量参数通常来自 query；单个 Pydantic 参数作为整体 body；header/cookie 要显式声明。重复 query 参数是否接收列表由类型契约决定。先列出每个字段的唯一来源，再处理默认值和覆盖规则。

`strict=True` 阻止 JSON 字符串 `"1990"`、布尔值等被强转成 int，`extra="forbid"` 拒绝未知字段；约束仍只覆盖形状，不去空白、不判断租户归属、不解决同 ID 冲突。`response_model` 在输出边界过滤、序列化并再次校验；返回结构不匹配是服务端契约错误，通常导致 5xx，不应伪装成请求 422。

先为每个字段指定唯一来源，再写路由。以下契约中 `tenant_id` 来自可信身份，`limit` 来自 query，订单列表来自 body；请求体里重复出现的 `limit` 是未知字段，而不是另一条覆盖规则。

| 请求片段 | 唯一来源 | 预期处理 |
| --- | --- | --- |
| `POST /reports?limit=2` | path 无动态段，query 提供 `limit` | 校验为正整数 |
| `{"orders":[...]}` | 单个 Pydantic 参数作为 body | 校验订单形状 |
| `{"limit":99}` 混入 body | 无合法来源 | `extra="forbid"` 拒绝，返回 422 |
| 请求体自报 `tenant_id` | 不可信输入 | 不用于授权；真实租户来自服务端身份 |

数据流因此是“解析来源 → 模型校验 → 可信身份与授权 → 业务”。422 有两个来源：模型在业务前拒绝形状非法的请求；形状合法但业务校验拒绝（如全空白 id）也映射为 422。同 ID 内容冲突应进入业务并映射为 409，不能提前改写成 422。

### 2.2 依赖注入提供可替换协作者

业务函数、外部客户端和可信身份由依赖边界提供。路由不读取环境，也不创建全局客户端；测试可替换依赖，同时仍执行真实授权与业务规则。本最小示例只演示业务与客户端注入，认证方案必须在部署前补齐。

依赖注入的价值可以用“同一业务、一个记录型替身”观察。替身只增加调用次数，不改变计算，因此测试同时能检查结果和调用边界。

```python
def build_report(rows):
    return sum(row["amount_cents"] for row in rows if row["status"] == "paid")

calls = []
def tracked_builder(rows):
    calls.append(1)
    return build_report(rows)

def endpoint(builder):
    rows = [
        {"amount_cents": 1990, "status": "paid"},
        {"amount_cents": 1000, "status": "pending"},
    ]
    return builder(rows)

print(endpoint(build_report), endpoint(tracked_builder), len(calls))
```

预期输出为 `1990 1990 1`。执行时路由依赖只负责取得协作者，真实 builder 与 tracked builder 得到相同输入并返回相同金额；替身额外记录一次调用。边界是替身若直接返回固定 1990，就只能证明 mock 被调用，不能证明订单规则；认证与授权也应作为独立依赖保留真实检查。

### 2.3 请求依赖的 yield 负责请求范围清理

用 `Depends` 注入带 `yield` 的依赖时，进入生成器以取得资源，端点结束后继续执行生成器尾部；释放放进 `finally`，异常和取消也会走到清理。默认依赖按请求缓存，同一请求多次 `Depends` 不一定重复创建；应用级客户端仍归 lifespan，不能在每个请求的 yield 中关闭。

生成器只能 yield 一次；yield 之前的失败还没有可释放资源，yield 之后则必须让清理覆盖异常路径。需要确认清理次数时，在正常、业务失败和取消三条路径分别记录事件。

依赖清理与响应发送的先后顺序取决于框架版本和依赖类型；需要精确顺序时用当前版本的集成测试固定，不能把“路由函数已返回”当作清理已完成。测试替身也要实现相同释放契约，否则会掩盖泄漏。

`yield` 依赖的清理路径可以用普通生成器先验证。正常返回和业务异常都必须在尾部释放资源。

```python
events = []

def request_resource():
    events.append("open")
    try:
        yield "connection"
    finally:
        events.append("close")

for fail in (False, True):
    events.clear()
    try:
        resource = request_resource()
        connection = next(resource)
        events.append("use")
        if fail:
            raise ValueError("business failure")
    except ValueError as exc:
        events.append(type(exc).__name__)
    finally:
        resource.close()
    print(fail, events)
```

预期输出为 `False ['open', 'use', 'close']` 和 `True ['open', 'use', 'ValueError', 'close']`。执行过程在 `next` 时进入生成器，在 `close` 或异常传播时执行 `finally`；边界是生成器只能 yield 一次，yield 之前的失败没有资源可释放，框架中的取消路径还要用集成测试确认清理次数。

### 2.4 应用级与请求级资源生命周期不同

共享 `AsyncClient` 在应用 lifespan 创建和关闭；请求身份、会话或流对象在请求范围使用。正常返回、异常和取消都要释放请求资源，一次请求不能关闭其他请求仍在使用的连接池。

同步路由可由框架安排在线程池；`async` 路由直接调用同步阻塞函数仍会占住事件循环。选择执行方式要看实际 I/O，不看函数名里有没有 `async`。同步路由中的全局可变状态仍可能竞争；`async` 路由必须显式 `await asyncio.to_thread(...)` 或改用异步客户端，不能把线程池当作无限资源。
CORS 只约束浏览器跨域访问，TLS 只保护传输；它们都不回答“当前调用者能否操作这份订单”。可信身份应来自服务端认证上下文，对象授权不能依赖请求体自报 `tenant_id` 或 `role`。

认证回答“你是谁”，授权回答“你能对哪个对象做什么”。认证依赖可以校验令牌，但每个订单仍要按可信身份、资源归属和动作检查权限；无法建立可信身份通常返回 401，身份有效但权限不足返回 403。OpenAPI 声明 security scheme 只是文档，不会自动执行检查。

## 3. 原理讲解与推导

### 3.1 薄适配层让多个入口共享同一规则

CLI 和 API 各自解析输入，但都把规范化后的订单交给 `build_report`。路由复制金额算法会产生第二个规则来源，使一次状态变更只更新一个入口。统一业务函数后，接口测试才能验证真正会复用的计算，而不是另一套示例逻辑。
授权也不能因此省略：模型合法只说明字段可进入业务，资源归属和动作权限仍由可信上下文决定。测试替身应保留真实授权规则，否则“通过”只证明 mock 按预期返回。

两个入口可以只共享一个最小规则函数。下面用 CLI 原始列表与 API 请求体两种适配输入，预期得到同一报告。

```python
def build_report(rows):
    return {"paid_amount_cents": sum(
        row["amount_cents"] for row in rows if row["status"] == "paid")}

def cli_adapter(raw_rows):
    return build_report(raw_rows)

def api_adapter(body):
    return build_report(body["orders"])

rows = [{"amount_cents": 1990, "status": "paid"},
        {"amount_cents": 1000, "status": "pending"}]
print(cli_adapter(rows) == api_adapter({"orders": rows}), cli_adapter(rows))
```

预期输出为 `True {'paid_amount_cents': 1990}`。执行过程分别解析入口输入，再调用同一个 `build_report`；边界是这个最小函数没有规范化、去重和授权，真实项目必须保留第12章规则与可信身份检查，不能把探针当成完整 API。

## 4. 示例与逐步走查

### 4.1 定义订单报告接口

#### 案例推进：严格输入只到达一次业务函数

先声明依赖：`uv add "fastapi>=0.115,<1"`。把下面保存为 `order_service/main.py`。

这是 `framework-example`：只做语法检查，本次不启动 FastAPI，也不访问示例域名。它依赖项目环境和 HTTPX，不能当作已运行的接口证据。

```python
# framework-example: F15
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from order_service.core import build_report, OrderConflict
class OrderIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str = Field(min_length=1)
    user: str = Field(min_length=1)
    amount_cents: int = Field(ge=0)
    status: Literal["paid", "pending", "cancelled"]
class ReportIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    orders: list[OrderIn]
class ReportOut(BaseModel):
    input_count: int
    order_count: int
    paid_amount_cents: int
def get_report_builder():
    return build_report
```

Pydantic 只负责输入形状；`id/user` 两端空白和同 ID 冲突仍由共享业务函数判断。依赖注入让测试可以记录调用次数，而不必替换金额计算。

### 4.2 用 lifespan 管理共享客户端

#### 案例推进：退出应用时关闭连接池

在同一文件继续添加下面代码；`/external-report` 复用第14章适配器和同一报告函数。

```python
from contextlib import asynccontextmanager
import httpx
from fastapi import Request
from order_service.external import fetch_orders, UpstreamError
@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(base_url="https://orders.example.test", trust_env=False) as client:
        app.state.http_client = client
        yield
app = FastAPI(lifespan=lifespan)
@app.post("/reports", response_model=ReportOut)
def create_report(body: ReportIn, builder=Depends(get_report_builder)):
    try:
        return builder([order.model_dump() for order in body.orders])
    except OrderConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
def get_http_client(request: Request):
    return request.app.state.http_client
@app.get("/external-report", response_model=ReportOut)
async def external_report(client=Depends(get_http_client)):
    try:
        return build_report(await fetch_orders(client, retries=1))
    except (OrderConflict, ValueError) as exc:
        raise HTTPException(status_code=502, detail="上游订单数据不符合契约") from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail="上游订单服务不可用") from exc
```

客户端只创建一次并跨请求复用；`async with` 保证应用退出时关闭。lifespan 把客户端挂在 `app.state`，请求侧经 `request.app.state` 读取；`request.state` 是每请求独立的命名空间，不会自动带上应用级对象。生产环境要把 base URL 放入配置，并在入口注入，而不是固定在代码里。

### 4.3 用 TestClient 走完整接口路径

#### 案例推进：分别验证成功、拒绝和清理

这是 `framework-example`：本次不启动 TestClient，只检查语法；它需要 FastAPI、HTTPX 与第12–14章模块，且不会访问真实订单服务。

```python
# framework-example: F15B
from fastapi.testclient import TestClient
calls = []
def tracked_builder():
    def builder(rows):
        calls.append(1)
        return build_report(rows)
    return builder
app.dependency_overrides[get_report_builder] = tracked_builder
with TestClient(app) as client:
    shared = client.app.state.http_client
    assert not shared.is_closed
    body = {"orders": [
        {"id": "A", "user": "Alice", "amount_cents": 1990, "status": "paid"},
        {"id": "B", "user": "Bob", "amount_cents": 1000, "status": "pending"},
        {"id": "A", "user": "Alice", "amount_cents": 1990, "status": "paid"}]}
    ok = client.post("/reports", json=body)
    assert ok.status_code == 200
    assert ok.json() == {"input_count": 3, "order_count": 2, "paid_amount_cents": 1990}
    assert calls == [1]
    calls.clear()
    for bad in ({"orders": [{"id": "A", "user": "Alice", "amount_cents": "1990", "status": "paid"}]},
                {"orders": [{"id": "A", "user": "Alice", "amount_cents": True, "status": "paid"}]},
                {"orders": [{"id": " ", "user": "Alice", "amount_cents": 1, "status": "paid"}]},
                {"orders": [{"id": "A", "user": "Alice", "amount_cents": -1, "status": "paid"}]},
                {"orders": [], "tenant_id": "b"}):
        assert client.post("/reports", json=bad).status_code == 422
    assert calls == [1]  # id=" " 形状合法，进入业务后被空白校验拒绝，计数一次
    conflict = client.post("/reports", json={"orders": [body["orders"][0],
        {"id": "A", "user": "Alice", "amount_cents": 1991, "status": "paid"}]})
    assert conflict.status_code == 409
app.dependency_overrides.clear()
assert shared.is_closed
```

`TestClient` 经过真实路由、模型验证、依赖和响应映射，并触发 lifespan；它仍不验证真实网络、反向代理和部署配置。上游 502 分支应在 `tests/test_api.py` 中通过依赖替身覆盖。`F15B` 的预期状态序列是 200、五个 422、一个 409；业务调用次数在合法请求后为 1。五个 422 中，字符串金额、布尔金额、负金额和额外字段四个是形状非法，模型在业务前拒绝，不产生调用；`id=" "` 长度为 1，通过 `min_length=1`，形状合法但业务去空白后拒绝并映射为 422，因此循环结束后计数是 1 而不是 0。退出上下文后 `shared.is_closed` 为真。
覆盖 502 时替换 `get_http_client`，让适配器抛出受控 `UpstreamError`，断言响应为 502 且正文不含内部异常。这样测试的是错误映射，不是 mock 掉订单报告计算。

接口证据还要区分层次：请求 `GET /openapi.json`，确认路径、请求体和 `ReportOut` 已声明，接入认证后再核验 security scheme；422 要区分来源，模型拒绝的错误位置指向请求字段且业务未调用，业务拒绝形状合法输入时携带业务错误信息；409 必须来自形状合法但冲突的业务数据；502 来自受控上游失败且正文已脱敏。OpenAPI 能证明契约被声明，不能单独证明运行时授权或部署可用。

## 5. 动手练习

### 本章累计任务：把同一订单业务接成服务

完成 `/reports` 与 `/external-report`，复用第12–14章函数。用 TestClient 覆盖 200、422、409、502，记录形状非法输入时业务未执行、空白字符串由业务拒绝仍返回 422；用替身验证上游失败，并断言 lifespan 退出后共享客户端关闭。记录启动命令，并明确本练习的身份方案不能直接作为生产认证。

## 6. 验收与自测

**验收命令：** 在项目根目录运行 `uv run --locked python -m pytest tests/test_api.py -q`；测试使用依赖替身，不访问真实订单服务。

### 6.1 先预测，再查看参考推导

请求模型已经通过，为什么仍不能据此授权？每个请求可以随意关闭共享 HTTP 客户端吗？

<details>
<summary>完成预测后查看解释</summary>

模型只证明数据形状合法，身份与对象权限必须由服务端检查。共享客户端由应用级所有者关闭，请求退出不能破坏其他请求正在使用的连接池。

</details>

### 6.2 用操作、预期结果与证据验收

| 操作 | 预期结果 | 证据 |
| --- | --- | --- |
| 发送合法、严格输入失败与同 ID 冲突 | 分别得到 200、422、409，形状非法不调用业务，空白字符串由业务拒绝 | 状态码、错误位置与业务调用计数 |
| 注入受控 `UpstreamError` | `/external-report` 返回脱敏 502 | 响应正文不含内部异常 |
| 进入并退出 TestClient 上下文 | lifespan 创建一次客户端，退出后关闭 | `app.state.http_client.is_closed` |

## 7. 面试问答与迁移

**问：为什么不在路由里直接写金额统计？**
答：CLI、API 和工具会需要同一规则。路由只做协议转换，统一业务函数才能让变更和测试覆盖所有入口。

**问：依赖注入和生命周期有什么关系？**
答：依赖决定协作者从哪里来，生命周期决定它何时创建和释放。测试替换边界时也要保留真实清理规则，不能只替换成一个永远不关闭的对象。

## 8. 本章小结与参考

- 请求模型先拒绝非法输入，业务冲突走独立错误路径。
- 路由复用 `build_report` 与 `fetch_orders`，不复制订单规则。
- 共享客户端由 lifespan 管理，TestClient 同时验证路由和清理。
- 本章交付可测试订单 API，第16章把跨请求状态放入持久化边界。

参考：[FastAPI 依赖](https://fastapi.tiangolo.com/tutorial/dependencies/)、[FastAPI 生命周期事件](https://fastapi.tiangolo.com/advanced/events/)。

[上一章](14-外部数据模型、HTTP与可靠调用.md) · [下一章](16-数据库、任务状态、幂等与审批.md)
