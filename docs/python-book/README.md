# Python、项目工程与 AI 开发实战教材

**面向有 Java 后端经验、希望转向 Python / AI 应用开发的学习者。**

本版将原有计划、原理、练习和项目规格组织为五卷30章。每章在同一文件中提供基础知识、原理、例子、练习、验收与面试追问，不要求来回翻阅旧日程才能上课。旧材料保留作来源与深入参考。

## 阅读方式与范围

1. 先读 [导读](00-guide.md)，再从当前未掌握章节顺序推进。
2. 每章统一为八部分：目标与前置 → 基础知识 → 原理 → 示例 → 练习 → 验收 → 面试迁移 → 小结参考。
3. 卷一按 [12主题周/60任务](../learning-plan/python-systematic.md)安排时间。完成后用后续各卷承接 [项目路线W04之后](../learning-plan/enterprise-ai-16-weeks.md)。章节不等于一晚或一周，难章可分多次。
4. 项目主线仍为订单工具、DocPilot、ProcureAgent；避免为每个概念新开独立项目。
5. Python 以当前项目3.12兼容语法为基线；第三方库按当前官方入口学习，实践时锁定实际版本，不承诺任意最新SDK与旧示例完全兼容。

“完整”指从语言到应用工程、Agent和面试的学习闭环，不穷尽全部计算机/AI学科。数学推导、训练与微调、GPU推理优化等设为 [扩展方向](appendix.md)，按目标岗位进一步学习。

## 示例与练习状态

- 卷一包含E01–E24原理实验和B01–B12独立基础示例，后续章节还有B18/B20/B21/B26等离线机制示例；示例供解释，练习需要你自己实现。
- 框架片段、项目契约、真实模型调用和部署需要对应依赖、数据与服务，不能当作已完成或已全链路验证的系统。
- 旧 `practice/python_ai_course/checks_*.py` 覆盖一部分基础任务，未实现时会失败；其他练习需按验收要求自行添加检查。
- 资料核对日期：2026-11-04。参考入口和 [版本与复习方法](appendix.md)放在附录。

## 卷一：Python 语言与原理

| 章节 | 内容 |
| --- | --- |
| 01 | [认识执行过程、对象与控制流](01-execution-objects.md) |
| 02 | [数字、金额、文本与编码](02-numbers-text.md) |
| 03 | [容器、推导式与数据转换](03-collections.md) |
| 04 | [函数、作用域、闭包与装饰器](04-functions-scope.md) |
| 05 | [迭代、生成器、异常与资源管理](05-iteration-resources.md) |
| 06 | [类、数据模型与协议](06-object-model.md) |
| 07 | [模块、文件、序列化与命令行](07-modules-files.md) |
| 08 | [标准库、时间、算法工具与数据库](08-standard-library.md) |
| 09 | [类型系统、校验模型与接口契约](09-typing-validation.md) |
| 10 | [测试、调试、日志与项目工具](10-testing-tools.md) |
| 11 | [异步、线程进程与性能边界](11-concurrency-performance.md) |
| 12 | [Python 综合项目与独立验收](12-python-capstone.md) |

## 卷二：项目工程与后端服务

| 章节 | 内容 |
| --- | --- |
| 13 | [环境、分层、配置与工程交付](13-engineering-structure.md) |
| 14 | [外部数据模型、HTTP 与可靠调用](14-http-models.md) |
| 15 | [FastAPI、接口模型与服务生命周期](15-fastapi.md) |
| 16 | [数据库、任务状态、幂等与审批](16-state-idempotency.md) |
| 17 | [部署、可观测性与可靠性](17-deployment.md) |

## 卷三：大模型、RAG 与单 Agent

| 章节 | 内容 |
| --- | --- |
| 18 | [大模型基础、消息与结构化输出](18-llm-foundations.md) |
| 19 | [文档解析、字段抽取与证据定位](19-document-extraction.md) |
| 20 | [RAG、Embedding、向量库与权限过滤](20-rag-baseline.md) |
| 21 | [混合检索、重排与 RAG 评测](21-rag-evaluation.md) |
| 22 | [Tool Calling 与手写 Agent Loop](22-agent-loop.md) |
| 23 | [LangGraph、状态、Checkpoint 与人工审核](23-langgraph.md) |

## 卷四：协议、Multi-Agent 与质量

| 章节 | 内容 |
| --- | --- |
| 24 | [MCP 与跨系统工具边界](24-mcp.md) |
| 25 | [Multi-Agent 的分工、并行与合并](25-multi-agent.md) |
| 26 | [AI 评测、提示注入、追踪与成本](26-ai-quality.md) |

## 卷五：综合项目与转行面试

| 章节 | 内容 |
| --- | --- |
| 27 | [项目实战一：DocPilot 从零到检索系统](27-docpilot-project.md) |
| 28 | [项目实战二：ProcureAgent 审查系统](28-procureagent-project.md) |
| 29 | [原理面试：语言、工程与 AI 的追问](29-interview-foundations.md) |
| 30 | [转行准备、项目讲述与系统设计面试](30-career-system-design.md) |

## 书后材料

- [导读与学习方法](00-guide.md)
- [术语、36张面试卡、模拟面试与扩展方向](appendix.md)
- [教材核验记录与范围](VALIDATION.md)
- [Python能力检查表](../learning-plan/python-competencies.md)
- [学习记录模板](../tutorial/learning-log.md)
