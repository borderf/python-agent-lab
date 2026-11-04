# 第14章　外部数据模型、HTTP 与可靠调用

[上一章](13-engineering-structure.md) · [全书目录](README.md) · [下一章](15-fastapi.md)

## 1. 学习目标与前置知识

统一参数校验、客户端生命周期和错误分类。前置：第9、11、13章。

## 2. 基础知识讲解

外部输入按字段、类型、范围和额外字段策略验证，内部领域模型表达计算语义。转换模式可能接受数字字符串，严格模式则按约定拒绝；选择必须与接口契约一致。

HTTP 调用经历 DNS/连接、响应状态、内容解析和业务校验。只在可重试条件、幂等性和预算允许时重试；连接/读取时限不能替代整个业务任务的总时限。

连接池由明确的拥有者创建和关闭。测试注入客户端与固定响应，真实环境另做少量集成验证。缓存还要考虑权限、版本和过期，不只按查询文字缓存。

## 3. 原理讲解与推导

边界失败必须保持语义；网络失败不等于“没有订单”。限制重试次数与总预算，避免故障放大。

### 项目化展开

### 第 07 课：TypedDict、dataclass 与 Pydantic

#### 理解

| 工具 | 本课程用途 | 需要记住 |
| --- | --- | --- |
| TypedDict | 描述内部订单字典的字段 | 静态提示，不做运行时验证 |
| dataclass | 保存配置、结果等对象 | 自动生成初始化等方法，本身不校验标注的类型 |
| Pydantic BaseModel | 校验文件/API/模型返回的外部数据 | 可以约束类型、范围、额外字段和序列化 |

Pydantic 可能默认进行类型转换。练习要求字符串金额报错，因此需要明确使用严格校验，而非假设所有模式都严格。

```python
from pydantic import BaseModel, ConfigDict, Field

class ExampleQuantity(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    quantity: int = Field(ge=0)
```

#### 练习

在 week02_clients.py 顶层定义 OrderModel，供第三周复用，再实现 validate_with_pydantic(raw)。保持第一周的外部行为：字段严格、非负金额、合法状态、去除名称空白、拒绝空名称、额外字段和 bool 金额。将通过的模型用 model_dump() 转成普通订单字典。

同一组输入分别经过手写校验和 Pydantic 校验，比较结果；失败时允许抛 ValueError 或其子类 ValidationError，不要求错误文字完全一致。

验收：合法数据结果相等；`"19900"`、199.0、True、缺字段、多字段都拒绝。运行 `-k validation`。

### 第 09 课：HTTP 客户端、错误与有限重试

#### 理解

一段请求依次经历连接、获取 HTTP 响应、解析 JSON、校验业务数据。它们会发生不同错误：连接/超时异常、4xx/5xx、JSON 解析错误、订单字段错误。

```python
import httpx

with httpx.Client(base_url="https://example.test", timeout=5.0) as client:
    # 真实使用时换成有权限访问的接口。
    response = client.get("/orders")
    response.raise_for_status()
    payload = response.json()
```

HTTPX 客户端使用上下文管理关闭连接池。timeout 的分项约束不等同于整个业务流程的总时限。不能对所有错误无条件重试：本课扩展只考虑幂等 GET 的临时网络失败，限制次数；数据校验错误不重试，涉及写操作时还要考虑幂等性。

#### 练习

实现 fetch_orders(client)：GET /orders，检查状态，解析 JSON，再调用严格订单校验。client 由调用方传入，函数不偷偷创建永久连接。

检查使用 HTTPX MockTransport，不访问真实网络：

```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])

with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
    assert fetch_orders(client) == []
```

验收：200 合法列表成功；500 抛 HTTPStatusError；超时保留 TimeoutException 类型；坏 JSON 或错误结构不变成空列表。运行 `-k http`。

### 重试不是简单的for循环

先判断错误类别与操作是否可安全重放，再判断剩余总预算，最后选择退避与抖动。一次请求最长5秒、最多3次，不等于整个业务严格15秒，因为还有连接等待、退避和处理时间。对总流程再设置截止时间，跨层传递剩余预算。

如果服务端可能已完成写入而客户端超时，需要幂等键或结果查询；不能把“没有收到响应”推断为“没有发生操作”。缓存键也须覆盖身份/租户、数据版本和会影响结果的参数。

## 4. 示例与逐步走查

### HTTPX离线边界示例

以下片段需要本章的HTTPX依赖，演示固定响应而不发外网请求：

```python
import httpx
def handler(request):
    return httpx.Response(200, json=[{"id":"A","amount_cents":10}])
with httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler), timeout=5.0) as client:
    response = client.get("/orders")
    response.raise_for_status()
    assert response.json()[0]["amount_cents"] == 10
```

下一步分别将handler改成500、ReadTimeout、坏JSON；先确认错误被正确分类，再接入字段校验。

## 5. 动手练习

实现同步与异步数据客户端，对 200、500、超时、坏 JSON 和不合法订单分别验证；给重试计数和总时限写案例。

## 6. 验收与自测

**行为验收：** 错误分类清楚，连接关闭，校验失败不执行业务动作，日志无密钥。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

HTTP 超时后能否直接重试 POST？连接池与每次新建客户端有什么代价？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://www.python-httpx.org/quickstart/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](13-engineering-structure.md) · [下一章](15-fastapi.md)
