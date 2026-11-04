# 第18章　大模型基础、消息与结构化输出

[上一章](17-deployment.md) · [全书目录](README.md) · [下一章](19-document-extraction.md)

## 1. 学习目标与前置知识

建立模型能力与工程限制的基本认识。前置：第9、11、14章。

## 2. 基础知识讲解

Token 是模型处理的离散单元，不固定等于汉字或单词。Embedding 将离散对象映射为向量；Transformer 用注意力等机制结合上下文更新表示。生成式语言模型逐步产生 token，采样策略影响输出，但没有“格式正确就事实正确”的保证。

上下文窗口限制一次可处理的信息，输出预算也消耗资源。训练、微调和推理分开理解：预训练学习通用分布，指令/偏好训练调整行为，推理利用给定上下文生成。RAG 增加外部证据，不修改模型参数；微调也不是随时更新私有事实的唯一选择。

消息角色、系统约束和供应商协议需要正确映射。Prompt 提供任务、输入边界、输出格式和可验证约束；结构化输出先解析、再校验，再检查业务事实。流式响应需要按事件/片段处理，不能当一个普通 JSON 整体读取。

## 3. 原理讲解与推导

把概率生成、证据来源、数据契约和确定性计算分开。KV cache 等推理缓存主要复用计算，不等同长期业务记忆；具体资源代价随模型和实现变化。

### 项目化展开

### 第 16 课：消息、模型边界与可替换实现

#### 理解

一次模型调用至少需要消息输入和结果输出；实际还涉及模型标识、超时、上下文长度、费用或计算资源。供应商返回格式不同，因此将其转换成课程内部的统一决策，避免业务函数直接依赖特定 SDK。

起始代码用 Model Protocol 声明“对象可以接收消息并返回决策字典”；实现无需继承 Protocol，只需提供相应的 __call__ 方法。这是结构化的接口约定，不负责运行时数据验证。

#### 离线练习

阅读 ScriptedModel：构造时传入一组返回结果，每次调用返回下一项，并记录收到的消息。自己写一次用户问候 → 模型返回 final 的流程，观察消息传递。

#### 真实模型练习

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

### 第 17 课：结构化结果与解析

#### 理解

“请返回 JSON”是要求，返回值仍需要程序校验。JSON 语法合法也可能缺字段、字段类型错误或选择不存在的工具。分开处理语法解析、结构校验和业务校验。

本课程内部协议只有两种决策：

```json
{"type":"tool_call","call_id":"call_1","name":"get_paid_total","arguments":{"user":"Alice"}}
```

```json
{"type":"final","content":"Alice 已支付 798.00 元。"}
```

字段恰好符合相应形状；字符串必需字段不能为空；arguments 必须是字典。具体工具是否存在、参数是否符合工具要求，留给工具执行层检查。

#### 练习

实现 parse_decision(payload)，不修改输入；拒绝未知 type、多字段、空 content、非字典 arguments 等。真实服务适配器先用 json.loads() 将文本解析成对象，再调用此函数；禁止 eval()。

Ollama 支持 format 参数及工具相关接口，但支持情况与模型有关。作为第一版，可以请求 JSON 格式并给出内部协议说明；如果后续使用原生工具调用，应另写适配器映射工具名称、参数、调用 ID 和工具结果，不能把内部协议当成供应商通用协议。

验收：运行 `-k decision`。扩展至少两条模型“看起来像 JSON 但不满足协议”的错误案例。

### 认识注意力、训练损失与推理资源

简化注意力为 `Attention(Q,K,V)=softmax(QKᵀ/sqrt(d_k))V`：Q与K产生匹配分数，softmax归一化，权重组合V。实际模型还有投影、多头、位置表示、残差、归一化和前馈层。因果语言模型通过掩码限制对未来位置的访问，示意公式不是完整Transformer。

下一token训练常以交叉熵约束目标token概率，简化为 `-log p(target | context)`。推理中的采样不是训练；上下文增加影响计算和缓存资源，长上下文也不保证模型有效使用所有证据。

TTFT是首token时间，生成吞吐与端到端耗时是其他指标。量化通过降低部分数值表示精度节约资源，但可能影响效果；KV cache复用注意力计算相关状态，不是业务知识库。模型版本、工具支持和上下文上限以实际服务契约验证，不背过时排行榜。

## 4. 示例与逐步走查

### 单查询注意力的数学小实验

```python
# book-example: B18
from math import exp, sqrt
query = [1.0, 0.0]
keys = [[1.0, 0.0], [0.0, 1.0]]
values = [10.0, 20.0]
scores = [sum(q*k for q,k in zip(query,key)) / sqrt(2) for key in keys]
largest = max(scores)
weights = [exp(score-largest) for score in scores]
weights = [value/sum(weights) for value in weights]
output = sum(weight*value for weight,value in zip(weights,values))
assert abs(sum(weights)-1.0) < 1e-12
assert weights[0] > weights[1] and 10 < output < 20
```

这个示例仅说明分数→归一化→加权组合，不能代表完整模型、训练或真实embedding。改变query后解释权重变化，再阅读模型基础资料。

## 5. 动手练习

用假模型完成消息与失败测试，再接一个真实服务；比较有无证据、不同输出约束的固定案例，记录用量和事实错误。

## 6. 验收与自测

**行为验收：** 不编造 token 计费和模型能力；坏 JSON、截断、超时和无证据有明确行为；一次请求可定位。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

RAG、微调、Prompt 各解决什么问题？temperature=0 是否就保证所有环境完全复现？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://huggingface.co/learn/llm-course/chapter1/1)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](17-deployment.md) · [下一章](19-document-extraction.md)
