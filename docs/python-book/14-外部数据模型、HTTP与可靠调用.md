# 第14章　外部数据模型、HTTP 与可靠调用

[上一章](13-环境、分层、配置与工程交付.md) · [全书目录](教材目录.md) · [下一章](15-FastAPI、接口模型与服务生命周期.md)

## 1. 学习目标与前置知识

前置：第9、11、13章。要能把外部响应转换为内部订单，并说明一次失败发生在哪一层。

**任务卡**
- 接收：第13章已锁定的 `order-service` 项目与统一 `build_report`。
- 只新增：HTTPX 异步客户端、响应适配器、错误分类和离线测试。
- 交付：`order_service/external.py` 与 `tests/test_external.py`。
- 验收：合法列表进入同一报告函数；500、超时、坏 JSON 和错误结构分别得到可区分错误，客户端全部关闭。

**本章从这里开始：** 外部订单服务返回 200，内容却可能是错误网页。连接、HTTP 状态、JSON 和业务结构是不同边界；先判断第一道失败边界，才能决定是否重试。

## 2. 基础知识讲解

### 2.1 从方法、状态、头和体理解一次 HTTP 交换

请求行包含方法、目标与 HTTP 版本；头部承载 `Content-Type`、`Accept`、认证、缓存和幂等键等元数据，体承载载荷。GET 通常只取表示且不应有业务写副作用；POST 常用于创建或触发动作，PUT 按协议语义应幂等而 PATCH 不保证；实现仍要核对实际契约，DELETE 也不能只凭方法名假定重复调用无副作用。

响应同样由状态行、头部和体组成。2xx 表示这一层成功，3xx 需要按重定向策略处理，4xx 通常要改请求或身份，5xx 表示服务端失败；429 表示限流。200 只说明 HTTP 交换成功，不证明 JSON、订单结构或业务金额正确。`Content-Type` 是解析线索而非信任凭证，仍要限制大小并验证结构。

3xx 不是最终业务响应：HTTPX 默认不自动跟随重定向，客户端要显式决定是否跟随；跨主机跳转还要重新检查 Authorization 是否会泄露，以及 POST 是否被改成 GET。重定向次数也计入总预算。

一次最小交换可以固定成下面的请求与响应。重点是逐段读取，而不是把整个响应当成“成功或失败”一个比特。

```http
GET /orders HTTP/1.1
Host: orders.example.test
Accept: application/json

HTTP/1.1 200 OK
Content-Type: application/json

[{"id":"A","amount_cents":1990}]
```

执行过程是：客户端发送方法与目标，服务端返回状态行、头和体；适配器先记录 `status=200`，再把 `Content-Type` 当作解析线索，最后才检查 JSON 列表中的订单字段。预期中间结果为 `method=GET`、`status=200`、`media_type=application/json`、`row_count=1`。边界情况是状态仍为 200，但体变成 HTML 或对象：这时前两步成功，后两步必须分别报解析错误和结构错误，不能返回空订单列表。

### 2.2 一次响应要穿过四层检查

传输层可能超时或断开；HTTP 层可能返回 500；解析层可能不是合法 JSON；结构层可能返回对象而非订单列表。任何一层失败都不能统一变成 `[]`，因为“没有订单”和“服务坏了”必须可区分。

状态成功后仍要检查结构，结构正确后再交给第12章 `build_report` 做字段与业务校验。这样外部适配器不复制金额、状态和去重规则。

外部 DTO 只描述 wire 契约：缺失字段与显式 `null`、未知字段、枚举值、金额单位和时间格式都要分别定义。适配器再把 DTO 转成内部订单；不要直接拿内部严格模型充当所有上游版本的模型，否则契约升级会同时破坏解析和业务。响应大小也应在读取前设上限。

四层检查可以用纯函数看到首个失败位置。输入只包含状态码和响应体，不依赖 HTTPX；四种固定输入对应四种可观察结果。

```python
import json

def classify(status, body):
    if 300 <= status < 400:
        return "redirect_error"
    if status >= 500:
        return "http_error"
    if status >= 400:
        return "request_error"
    try:
        rows = json.loads(body)
    except ValueError:
        return "parse_error"
    if not isinstance(rows, list):
        return "schema_error"
    return "ok"

cases = [
    (500, "<html>down</html>"),
    (302, "/orders"),
    (200, "<html>not json</html>"),
    (200, '{"orders": []}'),
    (200, '[{"id": "A"}]'),
]
for status, body in cases:
    print(status, classify(status, body))
```

预期输出依次为 `500 http_error`、`302 redirect_error`、`200 parse_error`、`200 schema_error`、`200 ok`。执行顺序必须先看状态，所以 500 的 HTML 不会被误报为解析错误，3xx 也不会被当成 2xx 去解析；200 的 HTML 才进入 JSON 解析，合法对象再进入列表结构检查。边界是 `ok` 仍只表示信封通过，订单缺字段、金额为布尔值或业务冲突要交给内部模型与 `build_report`，不能在这里返回空列表掩盖问题。

### 2.3 超时、重试和总预算不是一回事

HTTPX 通常提供 connect/read/write/pool 四类时限：分别约束建连、等下一块数据、写请求和等连接池名额；单次调用超时也不等于整个任务截止时间。重试只用于约定的临时故障，并受次数和剩余总预算限制。
读取超时通常限制等待下一块数据的时间，慢速响应可能每块都未超时却总时长很久。调用方应从任务开始计算 deadline，并把排队、重试和退避都计入；不能每重试一次就重新发放完整预算。

GET 通常可安全重放，但服务契约仍要确认；写操作超时后远端可能已经成功，必须用幂等键、状态查询或对账，不能直接重复提交。

可重试集合通常包括 408、429 和部分 5xx，例如 502/503/504；501/505 等多半不是临时容量问题。解析失败、结构错误和普通 4xx 不应盲目重试。遇到 `Retry-After` 的秒数或 HTTP 日期，先换算并受总 deadline 限制；无该头时用指数退避加全抖动，例如 `random.uniform(0, min(cap, base * 2**attempt))`，避免多个客户端同时重试。`retries` 表示额外重试次数，总尝试次数为 `retries + 1`；重试写操作还必须复用同一幂等键和载荷。下面的教学适配器只处理超时和 500/502/503/504，408/429 与 `Retry-After` 留给生产策略显式实现。

总预算可以用逻辑时钟观察，避免真实等待造成不稳定。假设任务 deadline 为 10，第一次调用耗时 4，第二次耗时 5，第二次后还要退避 2；第三次开始前预算已经耗尽。

```python
clock = 0
deadline = 10
durations = [4, 5, 2]
backoff = 2
for attempt, duration in enumerate(durations, 1):
    remaining = deadline - clock
    print("attempt", attempt, "remaining", remaining)
    if remaining <= 0:
        break
    clock += duration
    if attempt == 2:
        clock += backoff
print("budget-left", deadline - clock)
```

预期输出为 `attempt 1 remaining 10`、`attempt 2 remaining 6`、`attempt 3 remaining -1`、`budget-left -1`。执行过程在每次尝试前重算剩余预算，并把退避计入同一时钟；边界是逻辑时钟只解释顺序，真实实现必须用 `time.monotonic()`，且网络读取可能分多块，单次 read timeout 仍不等于总时长。

### 2.4 客户端由明确的所有者创建和关闭

`AsyncClient` 复用连接池，适合覆盖一组调用。它应在应用或适配器边界创建、注入并关闭；测试用 `MockTransport` 固定响应和异常，避免真实网络。替身证明客户端逻辑，不证明真实 DNS、TLS、认证或服务可用性。
日志记录状态类别、尝试次数和请求标识即可，不记录 Authorization、完整响应正文或用户敏感字段。错误消息可以说明失败层，但不能把内部堆栈和凭据直接交给调用方。

`client.get()` 默认读取完整响应并释放连接；使用 `client.stream()` 或手动消费响应流时，必须用 `async with` 或在 `finally` 中 `await response.aclose()`，否则连接可能无法回池。关闭响应不等于关闭共享客户端；池容量限制连接数，pool timeout 限制等名额的时间，二者都不限制上游业务并发。

连接池不是越大越好：限流、重试和池容量要一起设计，否则重试会放大拥塞。关闭客户端前先停止接收新请求并等待在途请求结束，否则会把它们一起中断。

## 3. 原理讲解与推导

### 3.1 检查顺序决定首个失败原因

如果先对 500 的 HTML 调用 `json()`，就会把服务故障误报成解析故障。先检查传输与状态，再解析和检查结构，错误才能保留可定位的原因；错误类别又决定能否重试。可靠调用不是“多重试几次”，而是先正确分类，再在总预算内执行有限次数。
分类错误还要保留给调用方：传输失败可进入临时故障策略，4xx 通常先修正请求或权限，结构和字段错误应修复契约。不能把所有异常都包装成“网络不好”。

把检查顺序画成一条单向数据流，就能预先写出每个输入的预期错误：

```text
连接/读取 → HTTP 状态 → JSON 解析 → 列表结构 → 订单字段 → build_report
   500          直接停止       200 才继续     对象在此失败    缺字段在此失败
```

对 `500 + HTML`，首个失败是状态；对 `200 + HTML`，首个失败是解析；对 `200 + {"orders":[]}`，首个失败是结构；对 `200 + [{"id":"A"}]`，信封通过但订单字段失败。四条路径都保留原响应类别与请求标识，后三类不会触发临时重试，除非调用方另有明确的契约恢复策略。

## 4. 示例与逐步走查

### 4.1 写受预算约束的异步适配器

#### 案例推进：只重试临时读取失败

先声明 HTTPX 运行依赖并更新锁：`uv add "httpx>=0.27,<1"`。把下面保存为 `order_service/external.py`。

这是 `framework-example`：静态检查会解析语法，但本次不执行，也没有访问真实订单服务。代码内的 `MockTransport` 只固定响应，运行它仍需项目已声明 HTTPX。

```python
# framework-example: F14
import asyncio
import time
import httpx
class UpstreamError(RuntimeError):
    pass
class TransportError(UpstreamError):
    pass
class HttpError(UpstreamError):
    pass
class ParseError(UpstreamError):
    pass
class SchemaError(UpstreamError):
    pass
async def fetch_orders(client, *, retries=1, timeout=5.0, deadline=None):
    if type(retries) is not int or retries < 0 or timeout <= 0:
        raise ValueError("重试次数或超时非法")
    budget_end = time.monotonic() + timeout * (retries + 1) if deadline is None else deadline
    for attempt in range(retries + 1):
        remaining = budget_end - time.monotonic()
        if remaining <= 0:
            raise TransportError("总预算耗尽")
        try:
            async with asyncio.timeout(remaining):
                response = await client.get("/orders", timeout=min(timeout, remaining))
                if response.status_code in {500, 502, 503, 504} and attempt < retries:
                    continue
                if response.status_code >= 500:
                    raise HttpError(f"订单服务状态:{response.status_code}")
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise HttpError(f"订单服务状态:{response.status_code}") from exc
                try:
                    rows = response.json()
                except ValueError as exc:
                    raise ParseError("订单响应不是合法JSON") from exc
                if not isinstance(rows, list):
                    raise SchemaError("订单响应必须是列表")
                return rows
        except (TimeoutError, httpx.TimeoutException) as exc:
            if attempt == retries:
                raise TransportError("订单服务超时") from exc
    raise AssertionError("不可到达")
async def main():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json=[{"id": "A", "user": "Alice", "amount_cents": 1990, "status": "paid"}]))
    async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
        rows = await fetch_orders(client)
    assert rows[0]["amount_cents"] == 1990
if __name__ == "__main__":
    asyncio.run(main())
```

`deadline` 是调用方传入的单调时钟绝对时间。每次重试都会重新计算剩余预算；省略时，教学实现用 `timeout × 总尝试次数` 建立本地保守上限。`asyncio.timeout(remaining)` 包住一次尝试的状态检查、响应读取和 JSON 解析，因此慢速分块也不能绕过整个 attempt 的截止时间；HTTPX 自身仍保留 connect/read/write/pool 的分阶段时限。这个实现没有加入退避和抖动，生产策略应共享调用方deadline，并把退避放在剩余预算内。`F14` 的替身主函数预期返回一条金额 1990 的订单、断言通过且控制台无输出；若 500 出现在最后一次尝试，预期是 `HttpError`，不会进入 JSON 解析。

### 4.2 用替身固定每种失败

#### 案例推进：逐项只改变一个响应

```python
import asyncio
import time
import httpx
from order_service.external import (
    fetch_orders, TransportError, HttpError, ParseError, SchemaError)
async def request(response=None, *, handler=None, retries=0):
    transport = httpx.MockTransport(handler or (lambda request: response))
    async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
        return await fetch_orders(client, retries=retries, deadline=time.monotonic() + 1)
async def main():
    valid = [{"id": "A", "user": "Alice", "amount_cents": 1990, "status": "paid"}]
    assert await request(httpx.Response(200, json=valid)) == valid
    cases = [(httpx.Response(500, text="down"), HttpError),
             (httpx.Response(302, headers={"location": "/orders"}), HttpError),
             (httpx.Response(200, text="<html>"), ParseError),
             (httpx.Response(200, json={"orders": valid}), SchemaError)]
    for response, error in cases:
        try:
            await request(response)
        except error:
            pass
        else:
            raise AssertionError("应得到对应错误")
    def late(request):
        raise httpx.ReadTimeout("late", request=request)
    try:
        await request(handler=late)
    except TransportError:
        pass
    else:
        raise AssertionError("超时应分类为传输错误")
    calls = []
    def recover(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=valid)
    assert await request(handler=recover, retries=1) == valid and len(calls) == 2
asyncio.run(main())
```

测试客户端由 `async with` 关闭，业务计算没有被 mock。500、302、坏 JSON、错误对象和超时都在首层失败；第一次503后第二次响应成功，才返回数据。预期结果是合法响应原样返回，四种固定响应分别抛 `HttpError`、`HttpError`、`ParseError`、`SchemaError`，超时抛 `TransportError`，恢复用例共调用两次并返回合法列表；控制台无输出。

### 4.3 接回同一订单业务

#### 案例推进：合法响应才进入报告

调用 `build_report(await fetch_orders(client, retries=1))`。字段错误、同 ID 冲突和金额汇总仍由第12章函数处理；适配器只把外部传输与信封错误转换为四类异常。不要在两处各写一份订单校验。

## 5. 动手练习

### 本章累计任务：可靠读取外部订单

实现 `fetch_orders`，用 MockTransport 覆盖合法、500、超时、坏 JSON、错误结构和临时失败后成功。断言尝试次数、总预算、错误类别与客户端关闭；合法结果必须进入原有 `build_report`，失败结果不能变成空报告。

### L21：HTTP 分层错误（P49）

用 HTTPX MockTransport 检查 GET /orders，分别返回合法列表、500、非 JSON 文本、结构错误对象，并模拟 ReadTimeout。状态检查、解析、校验依次发生；成功返回真正数据，其他情况保留可区分错误，客户端关闭责任清楚。

## 6. 验收与自测

**验收命令：** 在项目根目录运行 `uv run --locked python -m pytest tests/test_external.py -q`；测试不得访问真实网络。

### 6.1 先预测，再查看参考推导

MockTransport 全部通过后，为什么仍不能说外部服务已经可靠？

<details>
<summary>完成预测后查看解释</summary>

替身没有验证真实 DNS、TLS、代理、认证、服务部署和容量。它证明的是客户端在受控输入下如何分类、重试和关闭；真实集成需要另行记录证据范围。

</details>

### 6.2 用操作、预期结果与证据验收

| 操作 | 预期结果 | 证据 |
| --- | --- | --- |
| 用 MockTransport 返回合法、500、302、坏 JSON、错误对象并模拟超时 | 分别成功或得到四类可区分错误 | `tests/test_external.py` 参数化断言 |
| 让第一次 503、第二次成功 | 恰好两次尝试，返回合法订单 | 调用计数与剩余预算断言 |
| 检查客户端与测试网络边界 | 客户端关闭，测试不访问真实网络 | `is_closed` 断言与离线测试配置 |

## 7. 面试问答与迁移

**问：HTTP 超时后可以直接重试 POST 吗？**
答：不能。远端可能已经写入但回执丢失。只有服务明确提供幂等契约时才用同一动作键和载荷重试；否则查询状态、对账或转人工。

**问：为什么复用客户端？**
答：连接池能摊薄建连和 TLS 成本，但不会自动提升所有负载的吞吐。客户端由应用级所有者关闭，并设置池容量、等待时限和总预算。

## 8. 本章小结与参考

- 按传输、状态、解析、结构顺序检查，保留首个失败原因。
- 合法订单进入同一 `build_report`，外部错误不能伪装成空数据。
- 重试受错误类别、次数和总截止时间约束；写操作先确认幂等。
- 本章交付可靠出站客户端，第15章用同一业务规则提供入站 API。

参考：[HTTPX AsyncClient](https://www.python-httpx.org/async/)、[HTTP 重试语义](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)。

[上一章](13-环境、分层、配置与工程交付.md) · [下一章](15-FastAPI、接口模型与服务生命周期.md)
