# 第二周：工程基础与 HTTP（06–10）

[教程入口](README.md) · 起始代码：[week02_clients.py](../../practice/python_ai_course/week02_clients.py)

第一周检查通过后再开始。第二周使用 Pydantic 2 和 HTTPX；在现有项目根目录按需执行：

```powershell
uv add "pydantic>=2,<3" httpx
uv run python -m pytest practice/python_ai_course/checks_week02.py -q
```

uv add 会更新 pyproject.toml、uv.lock 和环境。教程提供的是依赖范围，实际版本由锁文件记录。首次需要联网，遇到下载失败先解决网络或索引问题，不要混用多个解释器安装。

## 第 06 课：模块、导入、配置与命令行入口

### 理解

模块就是可以导入的 Python 文件；包组织相关模块。导入时顶层代码会执行，所以文件读取、网络请求和启动服务应放在显式入口里。`python -m package.module` 按包结构运行，有助于理解导入路径。

`pyproject.toml` 描述项目、依赖与工具配置，uv.lock 记录解析后的版本，.venv 存放实际环境。不要把 .venv 或密钥加入 Git。

### 练习

把第一周 CLI 补成如下接口（文件由你创建）：

```powershell
uv run python -m practice.python_ai_course.cli --input practice/python_ai_course/data/orders.json --output report.json
```

使用 argparse：`--input` 必填，`--output` 可选；提供输出路径时以 UTF-8 写 JSON，否则打印。合法运行退出码 0，预期输入错误退出码非 0。只在 main() 里调用解析参数、读文件和展示，业务函数不读命令行参数。

验收：换输入文件无需改代码；`--help` 解释参数；导入模块不会生成 report.json；工作目录不同导致路径变化时能解释原因。

提示：不要同时改目录、金额模型和去重策略。每次重构后先检查原有行为。

## 第 07 课：TypedDict、dataclass 与 Pydantic

### 理解

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

### 练习

在 week02_clients.py 顶层定义 OrderModel，供第三周复用，再实现 validate_with_pydantic(raw)。保持第一周的外部行为：字段严格、非负金额、合法状态、去除名称空白、拒绝空名称、额外字段和 bool 金额。将通过的模型用 model_dump() 转成普通订单字典。

同一组输入分别经过手写校验和 Pydantic 校验，比较结果；失败时允许抛 ValueError 或其子类 ValidationError，不要求错误文字完全一致。

验收：合法数据结果相等；`"19900"`、199.0、True、缺字段、多字段都拒绝。运行 `-k validation`。

## 第 08 课：pytest、参数化、fixture 与替身

### 理解

测试由输入、动作、断言构成。断言列表长度为 2，仍可能漏掉“返回了错误的两条订单”。先断言业务结果，再关注实现细节。

```python
import pytest

@pytest.mark.parametrize("value, expected", [(0, "0.00"), (1, "0.01")])
def test_money_display(value, expected):
    from practice.python_ai_course.week01_orders import format_cents
    assert format_cents(value) == expected
```

fixture 提供可复用准备工作；tmp_path 给每个测试独立临时目录。mock/替身用于控制网络或模型边界，订单加法、去重这些核心逻辑应直接检查。

### 练习

1. 为 load_orders 写三个 tmp_path 测试：合法文件、非法 JSON、合法 JSON 但结构不合法。
2. 用参数化覆盖金额边界，增加自己想到的一种非法输入。
3. 故意把去重后再汇总改成汇总后再去重，确认至少一条测试失败，再恢复实现。
4. 检查两个测试是否共享可变样例；若共享，给每个测试独立副本。

验收：独立运行、调整顺序和重复运行结果一致。只为真实业务行为写断言，不把测试写成实现的逐行复制。

## 第 09 课：HTTP 客户端、错误与有限重试

### 理解

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

### 练习

实现 fetch_orders(client)：GET /orders，检查状态，解析 JSON，再调用严格订单校验。client 由调用方传入，函数不偷偷创建永久连接。

检查使用 HTTPX MockTransport，不访问真实网络：

```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])

with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
    assert fetch_orders(client) == []
```

验收：200 合法列表成功；500 抛 HTTPStatusError；超时保留 TimeoutException 类型；坏 JSON 或错误结构不变成空列表。运行 `-k http`。

## 第 10 课：配置、日志、闭包与接口边界

### 理解

配置作为输入传进来，避免模块导入时固定全局状态。实现 parse_settings(environ)：读取 REQUEST_TIMEOUT（默认 5.0 秒）与 MAX_CONCURRENCY（默认 3）；前者必须有限且大于 0，后者为正整数。无效配置抛 ValueError。

日志用于说明发生了什么：请求目标类别、状态、耗时、记录数；不要把 token、Authorization 或完整敏感订单直接输出。异常发生后由合适的边界统一记录，避免每层重复打印堆栈。

闭包可以保存外层变量，装饰器把函数传入再返回一个函数。先学会读以下结构：

```python
from functools import wraps

def announce(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        print("开始调用")
        return fn(*args, **kwargs)
    return wrapper
```

这里没有自动计时或重试。自己改成记录耗时，确保返回值与异常不被吞掉；同步装饰器不能直接当成异步装饰器使用。

练习：完成配置函数；给 CLI 增加基础 logging；为 HTTP 客户端添加可替换的数据来源。理解对象只需提供约定的方法就能被替换，第四周用 Protocol 明确这一约定。Generic 和复杂装饰器留待需要复用多种类型时学习。

选做：把配置结果包装成 dataclass，用错误类型调用构造函数，观察它是否会自动拒绝输入；再与 Pydantic 严格校验对比。是否需要冻结配置对象，由配置在程序中的用途决定。

验收：默认配置、显式合法配置和非法配置均有案例；测试不修改真实环境变量；日志没有凭据。运行完整 checks_week02.py。

阶段交付：文件与 HTTP 两种数据入口共用订单模型及统计规则，CLI 可配置、可记录错误，测试无需依赖外部服务。

参考：[uv 项目](https://docs.astral.sh/uv/guides/projects/)、[Pydantic 严格模式](https://docs.pydantic.dev/latest/concepts/strict_mode/)、[pytest](https://docs.pytest.org/en/stable/)、[HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports)。
