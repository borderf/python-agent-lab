# 第27章　MCP 与跨系统工具边界

[上一章](26-项目实战二：ProcureAgent审查系统.md) · [全书目录](教材目录.md) · [下一章](28-Multi-Agent的分工、并行与合并.md)

## 1. 学习目标与前置知识

**本章为按需选修。** 前置：第14章的HTTP边界、第24章的工具契约、第26章的ProcureAgent只读工具。没有跨进程共享需求时，可以跳过本章，直接进入第29章。

**任务卡**
- **接收上一章什么产物：** P200审查使用的可信项目、供应商和制度查询函数，以及工具轨迹。
- **本章只新增什么：** 一层发现、调用和结果转换协议，不重写金额、日期或授权规则。
- **交付什么：** 同一查询的本地/MCP结果对照，以及坏参数、越权和断连记录。
- **怎样验收：** 合法请求结果一致；模型伪造租户被拒；另一租户来源不可见；连接与子进程能清理。

**本章从这里开始：** 继续处理P200在2026-10-01的预付款上限查询。本地函数已经能返回20%及其来源，现在只问：另一个进程怎样发现并调用同一能力。

## 2. 基础知识讲解

### 2.1 Host、Client与Server不替代Agent Loop

Host组织模型应用和用户交互，Client维护与某个Server的协议连接，Server提供受控能力。Tools表示可调用操作，Resources表示可读取上下文，Prompts表示可发现模板；具体能力取决于协议与SDK版本。模型选择、协议传输、业务授权仍由不同层负责。

| 层次 | 负责的机制 | 不负责什么 |
| --- | --- | --- |
| Tool Calling | 模型提出工具名与参数，应用校验后执行 | 不规定跨进程发现、传输或服务端授权 |
| REST | 用HTTP资源与状态码暴露业务接口 | 不自动形成模型可发现的工具契约 |
| MCP | 在Host/Client/Server间发现并交换工具、资源与提示 | 不替代Agent Loop、业务幂等或租户隔离 |
| LangGraph | 组织状态、节点、暂停、检查点与恢复 | 不替代工具传输协议；节点内部仍可调用MCP或REST |

这些层次可以组合，但职责不能互相冒充：例如MCP Server可以调用REST，LangGraph节点可以消费MCP结果；增加一层就多一套版本、认证、序列化和故障边界。

### 2.2 适配器复用业务函数，身份来自可信会话

Schema只约束参数形状，description只帮助选择，二者都不授予权限。Client可以提前拒绝，但持有数据的Server必须再次检查主体、资源和业务日期。工具版本或Schema变化时，要重新比较本地与远端契约。

**服务端身份与最小权限：** 每个Client使用可审计的连接身份，Server把身份映射到租户、角色和资源范围，绝不采用模型填写的`tenant_id`。
- 校验令牌受众、有效期和连接来源；下游服务账号只授予当前工具所需动作，禁止用管理员账号兜底。
- 工具参数、Resource URI和下载地址都要做白名单与资源级授权，防止越权读取、路径遍历和任意URL请求。
- Prompts与Resources内容同样视为不可信输入；能力发现结果按调用者过滤，秘密留在Server配置或凭据服务，不返回给模型。
- Host限制暴露哪些Server与工具，Server限制能做什么；两层任一缺失都可能形成权限绕过。

#### 案例推进：先确认适配没有改变项目查询语义

```python
# study-example: S27A
def local_lookup(project_id, *, tenant):
    records = {"P200": {"tenant": "tenant-a", "name": "虚构超预算采购",
                        "budget_cents": 10000000}}
    item = records.get(project_id)
    if item is None:
        raise LookupError("项目不存在")
    if item["tenant"] != tenant:
        raise PermissionError("无权访问")
    return {"project_id": project_id, "name": item["name"],
            "budget_cents": item["budget_cents"]}

def adapter(arguments, trusted_tenant):
    if set(arguments) != {"project_id"} or not isinstance(arguments["project_id"], str):
        raise ValueError("参数不符合Schema")
    return local_lookup(arguments["project_id"], tenant=trusted_tenant)

assert adapter({"project_id": "P200"}, "tenant-a")["budget_cents"] == 10000000
try:
    adapter({"project_id": "P200", "tenant_id": "tenant-b"}, "tenant-a")
except ValueError:
    pass
else:
    raise AssertionError("模型不能注入身份字段")
```

这段代码只是业务适配器，不是完整MCP会话。真实处理器应调用同一个业务边界，并从已认证连接取得租户。

### 2.3 调用结束与未知效果要分开处理

发现失败、参数错误、断连和超时是不同故障。Client要关闭连接，Server要释放本次资源；stdio的stdout留给协议，调试信息走stderr。取消等待或关闭连接不表示已经发出的写操作停止，这类动作仍要审批、幂等和效果核对。

| 传输 | 生命周期与适用条件 |
| --- | --- |
| stdio | Client启动子进程并约定环境；初始化协商版本与能力；JSON-RPC走stdout、日志走stderr；结束时关闭stdin、等待退出，必要时按策略终止并回收进程。适合同机受控子进程。 |
| Streamable HTTP | Client连接服务URL并认证；初始化协商是否有会话，后续POST可返回JSON或SSE，GET是否可用取决于实现；支持时用DELETE终止会话。适合远程服务与多Client。 |
| 共同要求 | 两端保存并校验协议版本、能力和会话ID；设置连接、请求与总截止时间；断线后按能力重新初始化，不能假设旧请求或会话自动恢复。 |

HTTP重连、会话恢复和请求重放是不同问题；只有协议与服务端明确支持时才复用会话，已发送写请求仍须按动作键确认结果。

### 2.4 沿着一条JSON-RPC消息看清请求、响应与错误

以下用MCP的一次只读调用展示协议外壳，版本字段是示例值，实际必须与Server协商。输入是Client方法与参数；步骤依次为initialize协商、initialized通知、tools/list发现、tools/call执行；输出是对应id的result或error。请求发出后超时则是“本地未知”，不能伪造一条error响应。

**① 初始化请求：** Client声明协议版本与自身能力。

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"docpilot-learner","version":"1.0"}}}
```

**② 初始化响应：** Server返回协商版本、能力与身份；随后Client发送不带id的`initialized`通知。

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"procure-tools","version":"1.0"}}}
```

**③ 正常工具调用与响应：** `tenant-a`来自已认证连接，不出现在模型参数中；`structuredContent`是本实验约定的结构化结果，Client仍要按自身输出契约校验。

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_prepayment_limit","arguments":{"as_of":"2026-10-01"}}}
```

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"limit_percent\":20,\"source_id\":\"policy-a-current\"}"}],"structuredContent":{"limit_percent":20,"source_id":"policy-a-current"},"isError":false}}
```

**④ 参数错误与业务拒绝：** 多传`tenant_id`属于参数不合法；即使参数合法，另一租户来源也由Server授权拒绝。错误中的id必须与请求相同，内部堆栈和资源存在性不能泄露。

```json
{"jsonrpc":"2.0","id":4,"error":{"code":-32602,"message":"Invalid arguments","data":{"stable_code":"INVALID_ARGUMENTS"}}}
```

| 边界 | 输入/观察 | 输出 | 何时失败 | 验收 |
| --- | --- | --- | --- | --- |
| 发现 | tools/list响应 | 当前身份可见工具清单 | 断连或版本不兼容 | 清单不含未授权能力 |
| 参数 | tools/call参数 | result或-32602 | 业务调用前 | 坏参数调用次数为0 |
| 授权 | 连接身份、来源URI | 稳定业务拒绝 | Server资源检查 | 另一租户内容为零 |
| 发送后未知 | 已发出但超时/断连 | `EFFECT_UNKNOWN` | 无法证明远端状态 | 写操作先对账，不盲重放 |
| 清理 | 客户端关闭 | 子进程/会话终止 | 退出等待超时 | stdout无日志污染，资源回收 |

把上述分类做成离线判定器，便于在真实SDK实验前统一错误码：

```python
def classify_failure(stage, error_code=None):
    if stage == "validation":
        if error_code != -32602:
            raise ValueError("参数错误必须映射到-32602")
        return {"stable_code": "INVALID_ARGUMENTS", "retry": "none", "business_attempts": 0}
    if stage == "authorization":
        return {"stable_code": "PERMISSION_DENIED", "retry": "none", "business_attempts": 0}
    if stage == "before_send":
        if error_code == -32601:
            return {"stable_code": "METHOD_NOT_FOUND", "retry": "none", "business_attempts": 0}
        return {"stable_code": "TRANSPORT_UNAVAILABLE", "retry": "bounded_reinitialize",
                "business_attempts": 0}
    if stage == "after_send":
        return {"stable_code": "EFFECT_UNKNOWN", "retry": "read_only_or_reconcile",
                "business_attempts": "unknown"}
    raise ValueError("未知失败阶段")

assert classify_failure("validation", -32602) == {
    "stable_code": "INVALID_ARGUMENTS", "retry": "none", "business_attempts": 0}
assert classify_failure("authorization")["stable_code"] == "PERMISSION_DENIED"
assert classify_failure("before_send", -32601)["retry"] == "none"
assert classify_failure("after_send")["retry"] == "read_only_or_reconcile"
try:
    classify_failure("validation", -32601)
except ValueError:
    pass
else:
    raise AssertionError("方法不存在不能冒充参数错误")
print(classify_failure("after_send"))
```

预期最后一行输出为`{'stable_code': 'EFFECT_UNKNOWN', 'retry': 'read_only_or_reconcile', 'business_attempts': 'unknown'}`。参数错误在业务调用前停止且不重试；授权失败不泄露资源；发送前断连可有界重建连接；发送后未知只能对只读调用重试或对写调用按动作键核对。`business_attempts="unknown"`是关键：本地没有回执，不代表Server没有执行。最后一段测试确认`-32601`不能被静默映射成参数错误。

**判定对错：** 正常结果与本地函数一致、坏参数零调用、越权零内容、发送后未知不盲重放且连接清理，五项齐全才通过；只验证一次正常tools/call不通过。

## 3. 原理讲解与推导

### 3.1 协议统一交互外壳，业务语义仍要显式映射

同一工具从本地函数变成跨进程调用，只改变发现、序列化和生命周期。若远端允许了本地拒绝的租户，或把“未找到”改成“无风险”，问题就在适配或授权映射，而不是模型是否读懂工具说明。

**错误映射与截止时间：** 协议错误、业务拒绝和传输未知要使用不同稳定错误码，不能统一返回“调用失败”。
| 故障 | 映射与恢复 |
| --- | --- |
| 方法不存在、参数不合法 | 返回协议或校验错误并记录调用ID；修正前不重试，不泄露堆栈或内部路径 |
| 未认证、越权、资源不存在 | 返回稳定的业务拒绝；按安全策略隐藏资源存在性，不放宽过滤重试 |
| 已发送后超时或断连 | 标记结果未知；只读调用按原身份重试，写调用先查动作键和效果，禁止盲重放 |

总截止时间要传给Server并覆盖重试与排队；这里可放在双方约定的业务参数或元数据中，不能把它误当成MCP标准取消语义。Client取消只是协作信号，不保证远端计算或副作用停止。只有两个以上独立进程或客户端需要发现、认证和共享能力，且能承担版本与运维成本时，才把本地函数迁到MCP；否则保留本地调用。

## 4. 示例与逐步走查

#### 案例推进：第一步，固定同一业务问题的本地答案

P200使用`tenant-a`和`as_of=2026-10-01`。本地`lookup_limit`先按租户、业务日期和可信来源过滤，再要求恰好一条付款制度，结果应为：

```json
{"limit_percent": 20, "source_id": "policy-a-current"}
```

项目与供应商查询沿用第26章工具，只是执行位置移到Server。REST可以继续承载内部业务，MCP Server负责包装，不必在协议层再维护一份采购规则。

#### 案例推进：第二步，通过真实stdio Client调用同一制度工具

仓库实验使用锁文件中的MCP Python SDK 1.x。下面代码需要可选的`mcp`依赖组；它建立子进程、初始化、发现工具、调用并关闭连接。

```python
# framework-example: S27B
import asyncio
import json
from practice.integration_labs.mcp_client import run

result = asyncio.run(run())
assert result["result"] == {"limit_percent": 20, "source_id": "policy-a-current"}
assert result["local_equal"] and result["identity_injection_rejected"]
assert result["other_tenant_hidden"]
print(json.dumps(result, ensure_ascii=False))
```

预期JSON中的工具清单只含两个只读能力，且三个布尔检查均为true。这个实验固定使用`tenant-a`教学身份，不能直接当作多用户认证实现。此代码块保留为`framework-example`，本次文档修改未验证外部SDK运行；必须安装`mcp`依赖组并执行6节命令后，才能把结果写成实测。

#### 案例推进：第三步，用同一组反例检查协议边界

| 输入或故障 | 预期 | 首先检查 |
| --- | --- | --- |
| 参数多出`tenant_id` | Schema拒绝，业务调用0次 | 是否信任模型自报身份 |
| 请求`policy-b-current` | 不返回来源内容 | Server侧资源授权 |
| 日期不合法或制度不唯一 | 明确错误，不猜上限 | 输入模型与版本选择 |
| 发现失败、断连或超时 | 明确分类并关闭资源 | 会话生命周期与清理 |

工具出现在`tools/list`中只说明可发现，不说明当前用户可执行。协议返回超时也不说明远端没有效果。

## 5. 动手练习

### 本章累计任务：按需增加协议适配

把P200使用的一项只读能力接入真实跨进程工具协议，保留原业务函数。对同一正常、坏参数和越权样本分别运行本地与MCP路径，保存结果、错误分类和清理记录；没有共享需求时不引入这一层。真实实验入口见[项目装配手册](../project-practice/从实验到项目交付.md#将同一只读能力接入-mcp)。

## 6. 验收与自测

**验收命令：** 在仓库根目录运行已有实验，不新增依赖。

```powershell
uv run --frozen --group mcp python -m practice.integration_labs.mcp_client
```

预期输出可解析JSON，`local_equal`、`identity_injection_rejected`和`other_tenant_hidden`均为true，进程正常退出。

**判定对错：** 三个布尔均为true且子进程正常清理才通过；只展示tools/list、把参数Schema当授权，或未实跑却写“已验证”，均不通过。

### 6.1 先预测，再查看参考推导

Server列出了`get_prepayment_limit`，是否任何调用者都能读取制度？

<details>
<summary>完成预测后查看解释</summary>

不是。发现能力不等于执行授权。宿主控制暴露范围，Server还要根据可信身份检查租户、业务日期和具体来源；Schema与工具描述都不能替代这项检查。

</details>

## 7. 面试问答与迁移

**问：MCP、Tool Calling和REST分别解决什么？**
答：MCP约定Client/Server如何发现和交换能力，Tool Calling表示模型提出工具请求，REST组织HTTP资源接口。它们可以组合，例如MCP Server内部调用REST；职责不会因此合并。

**问：什么时候保持本地函数更合适？**
答：只有同进程使用、没有互通或独立部署需求时，本地函数通常更简单。需要跨客户端共享时，再衡量发现、认证、版本、序列化和故障成本；协议不会自动带来幂等或安全。

**问：关闭Client能取消远端写入吗？**
答：只能确认本地连接和等待结束。远端可能已经提交，必须按动作键查询状态并核对效果；需要撤销时使用业务系统明确提供的取消契约。

## 8. 本章小结与参考

- MCP只新增跨进程交互层，ProcureAgent的业务规则与授权边界不变。
- Host组织应用，Client维护连接，Server提供能力；模型循环仍在应用侧。
- Schema约束形状，可信身份与资源授权决定能否执行。
- 断连、超时和取消不等于外部效果停止；写操作继续使用审批、幂等与对账。
- 没有共享需求就保留本地调用；有分工假设时再进入[第28章](28-Multi-Agent的分工、并行与合并.md)。

参考：[MCP架构](https://modelcontextprotocol.io/docs/learn/architecture)、[真实Client/Server实验](../project-practice/从实验到项目交付.md#将同一只读能力接入-mcp)。SDK版本以锁文件为准。

[上一章](26-项目实战二：ProcureAgent审查系统.md) · [下一章](28-Multi-Agent的分工、并行与合并.md)
