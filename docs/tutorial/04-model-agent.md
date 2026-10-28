# 第四周：模型、工具与 Agent（16–20）

[教程入口](README.md) · 起始代码：[week04_agent.py](../../practice/python_ai_course/week04_agent.py) · 假模型：[fake_model.py](../../practice/python_ai_course/fake_model.py)

本章核心练习离线即可完成，重点是自己实现与验证调用流程。假模型不会理解语言，只按脚本返回结果；它适合检查代码，不能证明真实模型表现。真实模型适配与人工验收同样要完成。

## 第 16 课：消息、模型边界与可替换实现

### 理解

一次模型调用至少需要消息输入和结果输出；实际还涉及模型标识、超时、上下文长度、费用或计算资源。供应商返回格式不同，因此将其转换成课程内部的统一决策，避免业务函数直接依赖特定 SDK。

起始代码用 Model Protocol 声明“对象可以接收消息并返回决策字典”；实现无需继承 Protocol，只需提供相应的 __call__ 方法。这是结构化的接口约定，不负责运行时数据验证。

### 离线练习

阅读 ScriptedModel：构造时传入一组返回结果，每次调用返回下一项，并记录收到的消息。自己写一次用户问候 → 模型返回 final 的流程，观察消息传递。

### 真实模型练习

可以使用已有可用的模型服务。若本机已安装 Ollama 并准备了适合硬件的模型，先调用它的 /api/chat；模型名称从环境变量 OLLAMA_MODEL 读取，不照抄文档里的示例模型去下载。

```python
import os
import httpx

with httpx.Client(base_url="http://localhost:11434", timeout=30.0) as client:
    response = client.post("/api/chat", json={
        "model": os.environ["OLLAMA_MODEL"],
        "messages": [{"role": "user", "content": "用一句话解释订单去重。"}],
        "stream": False,
    })
    response.raise_for_status()
    print(response.json()["message"]["content"])
```

stream=False 时按单个 JSON 响应解析；不能把默认流式响应直接当成一个 JSON 文档。没有本地模型时也可选远程服务，按其官方文档实现同样的边界。凭据由环境变量提供，不写入源码或学习记录。

验收：记录一次输入、输出、耗时和可获得的用量；关闭服务或设置无效模型时，错误能传给调用者。不要在每次单元测试里请求真实模型。

## 第 17 课：结构化结果与解析

### 理解

“请返回 JSON”是要求，返回值仍需要程序校验。JSON 语法合法也可能缺字段、字段类型错误或选择不存在的工具。分开处理语法解析、结构校验和业务校验。

本课程内部协议只有两种决策：

```json
{"type":"tool_call","call_id":"call_1","name":"get_paid_total","arguments":{"user":"Alice"}}
```

```json
{"type":"final","content":"Alice 已支付 798.00 元。"}
```

字段恰好符合相应形状；字符串必需字段不能为空；arguments 必须是字典。具体工具是否存在、参数是否符合工具要求，留给工具执行层检查。

### 练习

实现 parse_decision(payload)，不修改输入；拒绝未知 type、多字段、空 content、非字典 arguments 等。真实服务适配器先用 json.loads() 将文本解析成对象，再调用此函数；禁止 eval()。

Ollama 支持 format 参数及工具相关接口，但支持情况与模型有关。作为第一版，可以请求 JSON 格式并给出内部协议说明；如果后续使用原生工具调用，应另写适配器映射工具名称、参数、调用 ID 和工具结果，不能把内部协议当成供应商通用协议。

验收：运行 `-k decision`。扩展至少两条模型“看起来像 JSON 但不满足协议”的错误案例。

## 第 18 课：把业务函数包装为工具

### 理解

工具描述让模型知道能请求什么操作；是否允许执行、参数是否合法和结果是什么，由程序决定。本课工具只查询注入的订单，不执行模型提供的任意 Python 或命令。

实现 execute_tool(name, arguments, orders)，只允许以下两种调用：

| 工具 | 参数（恰好这些字段） | 返回结果 |
| --- | --- | --- |
| get_paid_total | {"user": 非空字符串} | {"user": 名称, "found": bool, "paid_count": int, "paid_amount_cents": int} |
| get_order | {"order_id": 非空字符串} | {"found": bool, "order": 订单或 null} |

先按统一规则去重，冲突抛 ValueError；user/order_id 参数去掉两端空白。不存在用户返回 found=False、金额与数量为 0；Bob 存在而未支付，返回 found=True、金额与数量为 0。未知工具和错误参数抛 ValueError。

### 练习

先直接调用工具确认 Alice 为 79800 分、paid_count 为 2；查询 Bob 和不存在用户；查询不存在订单。再尝试额外参数、空名称、未知工具，确认均不会误执行。

验收：运行 `-k tool`。金额由已有订单计算函数得到，模型仅负责选择工具并组织说明。

## 第 19 课：完成调用循环、错误与预算

### 理解

一次工具调用后，程序要把执行结果放回消息，让模型决定继续还是结束。上限是防止无限循环的机制；它不能防止单次网络调用永久阻塞，真实适配器仍需要请求超时。

run_agent(question, orders, model, max_steps=5) 的约定：

1. 初始化 system 和 user 消息，system 说明工具协议和规则；不要把凭据塞进提示。
2. 每轮调用 model(messages)，再 parse_decision；一次模型调用计一步，最后的 final 也计一步。
3. final 返回结果字典：answer、steps、tool_calls、trace。tool_calls 是尝试执行工具的次数。
4. tool_call 先追加 assistant 决策消息，再执行白名单工具；追加 tool 消息，含 call_id、name 和 content。
5. 成功的 content 是 {"ok":true,"data":结果}；工具 ValueError 转为 {"ok":false,"error":简短说明} 回传，其他未知异常继续抛出。
6. trace 记录每次工具消息，以便检查是否真正执行；执行中不修改输入订单。
7. 达到 max_steps 仍无 final，抛 RuntimeError；非法决策抛 ValueError；max_steps 必须是正整数，拒绝 bool。

本课消息是内部记录格式：assistant.content 可以是决策字典，tool.content 可以是结果字典；真实模型适配器需要转换为该服务要求的消息格式。

### 练习

用 ScriptedModel 提供两步：请求 Alice 金额，再返回 final。确认模型第二次收到的最后消息是工具计算结果。再制造未知工具、模型一直要求调用工具、输出非法结构的情况，逐个检查退出或恢复行为。

验收：运行 `-k agent`。不能直接根据 question 中出现 Alice 就硬编码最终回答，也不能跳过工具执行把假模型的最终文字当成计算证据。

## 第 20 课：评估、接口与后续方向

### 理解

单次问答成功不足以证明系统可靠。评估要明确问题、期望行为、事实来源和错误类型。离线检查控制程序逻辑；真实模型评估检查工具选择、参数提取和回答是否忠于数据。

### 必做练习

1. 完成 checks_week04.py，并补充至少两条自己设计的失败案例。
2. 使用 data/evaluation_cases.json 中的场景做人工验收，记录模型、配置、答案、工具轨迹和成功/失败原因；不要只记一个总分。
3. 为真实模型实现适配器，将内部消息转换成服务消息，将返回转换成决策，校验后再进入循环。运行固定场景，检查用量和耗时；禁止假设模型天然会遵守协议。
4. 将已完成助手封装成 POST /chat，请求为 {"question":"..."}；返回 answer 和可检查的工具轨迹。给模型请求和整体任务设置合理预算；接口测试替换模型，不依赖真实推理。
5. 比较 Alice、Bob、未知用户、未知订单、无关问候、冲突数据和超出循环上限等场景。对金额问题逐项核对工具结果，格式正确不代表事实正确。

### 选做：检索与 RAG

有退款规则、操作手册等文档问题时，先做本地关键词检索：返回片段和文件来源，再让模型根据片段回答。为“没有证据”“检索到相似但无关内容”设置案例，再考虑向量检索。订单金额仍调用计算工具。

### 阶段交付

一份能启动的助手、固定评估场景、接口使用说明，以及当前局限：支持哪些问题、数据来自哪里、遇到冲突和模型错误怎么办。本文覆盖入门闭环；面向真实用户时还需按业务补充身份与数据访问控制、部署、监控和更完整评估。

参考：[Ollama Chat API](https://docs.ollama.com/api/chat)、[Ollama 结构化输出](https://docs.ollama.com/capabilities/structured-outputs)、[工具调用](https://docs.ollama.com/capabilities/tool-calling)、[Python Protocol](https://docs.python.org/3.12/library/typing.html#typing.Protocol)。
