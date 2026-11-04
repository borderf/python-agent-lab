# 第15章　FastAPI、接口模型与服务生命周期

[上一章](14-http-models.md) · [全书目录](README.md) · [下一章](16-state-idempotency.md)

## 1. 学习目标与前置知识

把业务库封装成可测试接口。前置：第12–14章。

## 2. 基础知识讲解

路径与查询参数描述资源和过滤条件，请求体模型描述提交数据，响应模型表达对外契约。依赖注入提供身份、仓储和客户端，路由不复制领域计算。

async 路由适合异步 I/O；同步阻塞调用必须有清楚执行边界。生命周期用于建立与关闭连接池，不能每个请求建立永不关闭的全局资源。

认证确认身份，授权判断当前身份是否能操作某资源。客户端自报 tenant_id/role 不能代替可信身份；错误状态码与日志要保留必要信息且不泄露内部细节。

## 3. 原理讲解与推导

API 是业务边界，不是给现有函数简单加装饰器。请求处理、取消、生命周期与资源所有权需一致。

### 项目化展开

### 第 13 课：请求模型与 FastAPI 路由

#### 理解

FastAPI 路由负责把 HTTP 请求转换成业务调用，Pydantic 模型负责外部数据结构，纯业务函数负责计算。不要在路由里复制一份订单规则。

实现 create_app(orders)，注入基础样例作为只读查询来源。工厂函数返回 app，便于测试用不同数据创建应用。接口契约为：

| 接口 | 输入 | 成功结果 | 错误 |
| --- | --- | --- | --- |
| GET /health | 无 | 200，{"status":"ok"} | 无 |
| GET /reports | 可选 query user | 200，该用户或全部订单的报告 | 指定用户不存在：404 |
| POST /reports | JSON {"orders":[订单...]} | 200，提交订单的报告 | 结构/字段不合法：422；同 ID 冲突：409 |

请求模型复用第二周的 OrderModel，额外字段和错误金额类型均拒绝。GET 不修改注入数据，POST 只分析本次提交数据，不保存为全局状态。

验收：空 orders 合法，返回零统计；Bob 存在但已支付金额为 0，不能当作用户不存在。先完成 health，再接两个报告接口。

### 第 14 课：接口测试与错误边界

#### 理解

TestClient 可以在进程内调用 app，无需真正监听端口。业务单元测试检查计算；接口测试进一步检查请求校验、状态码和响应结构。

```python
from fastapi.testclient import TestClient

with TestClient(create_app([])) as client:
    response = client.get("/health")
    assert response.status_code == 200
```

409 用于本课程定义的冲突，422 用于不满足请求模型的数据。不要把所有异常都转换成 200，也不要把未知内部错误都说成用户参数错误。

#### 练习

先运行提供的 API 检查，再自己补：GET user=Bob、POST 空列表、POST 额外字段、请求体缺少 orders；每条写出期望状态和核心字段。

验收：接口与第一周报告输出一致；冲突返回 409，类型错误返回 422。运行 `-k api`。

### 第 15 课：集成、调试与可选持久化

#### 理解

有了函数和路由，还需要解决运行与资源生命周期。异步路由不能直接执行耗时的同步 I/O；同步业务可选同步路由、线程边界或异步客户端。连接池应有明确创建与关闭位置。

#### 必做练习

自己创建 `practice/python_ai_course/api.py`：从已校验文件构建 app，并导出名为 app 的变量。为简单本地演示可在明确入口加载；扩展到需要连接池时再学习 lifespan 管理资源。不要让纯计算模块导入时访问网络。

```powershell
uv run uvicorn practice.python_ai_course.api:app --reload
```

访问 /docs，实际请求 health、全部报告和 Alice 报告。README 记录启动命令与一份请求/响应。重启后重新加载源数据符合本练习的只读设计。

#### 选做：SQLite

如果希望保存订单，再添加 sqlite3 存储练习：参数化 SQL、主键、事务、连接关闭和临时数据库测试。先在本地 SQLite 做通，再根据现有业务选择 MySQL/Redis 等。不要把数据库客户端更换和异步接口重构放在同一次改动中。

验收：完整第三周检查通过，服务可手动启动；能从一个失败请求定位是模型校验、订单规则还是资源调用出了问题。

参考：[asyncio 任务、取消和超时](https://docs.python.org/3.12/library/asyncio-task.html)、[同步原语](https://docs.python.org/3.12/library/asyncio-sync.html)、[FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)、[FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)。

### 生命周期与依赖的责任链

请求依赖可以获取身份和仓储，应用生命周期创建可复用连接池。请求结束需要释放本次资源，应用退出需要关闭共享池。不要让一个请求关闭其他请求仍使用的全局客户端。

响应模型既是文档也是对外字段边界；内部对象的密码、访问令牌和内部错误不应原样序列化。认证与授权分别测试：有效登录用户也可能无权读取指定文档。

## 4. 示例与逐步走查

### 最小请求模型与接口

以下需要FastAPI、Pydantic 2，接口测试还需要HTTPX；这里只演示请求边界：

```python
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
class Amount(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    cents: int = Field(ge=0)
app = FastAPI()
@app.post("/amounts")
def inspect_amount(body: Amount):
    return {"cents": body.cents}
```

提交整数1正常，字符串"1"、True、负数、额外字段都应被校验拒绝。再将业务函数和身份依赖注入路由，避免路由逐渐承担全部规则。

## 5. 动手练习

完成订单 health/report 接口和接口测试，增加可信身份依赖与跨租户拒绝案例；手动启动并从 /docs 请求。

## 6. 验收与自测

**行为验收：** 非法数据422、未知资源404、业务冲突409等按项目约定一致；请求之间不共享可变状态。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

依赖注入如何便于测试？为什么不能在 async 路由直接放同步阻塞请求？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://fastapi.tiangolo.com/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](14-http-models.md) · [下一章](16-state-idempotency.md)
