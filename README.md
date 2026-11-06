# python-agent-lab

一个以项目练习为主的学习仓库，记录从 Java 后端到 Python / AI 应用，并向软件架构、产品型工程师与创业发展的过程。

## 学习入口

- [三套独立教材与双方向学习导航](docs/学习导航.md)
- [Python、项目工程与AI：五卷30章](docs/python-book/教材目录.md)
- [软件架构：四篇14章，含工作簿与综合实战](docs/architecture-book/教材目录.md)
- [产品型工程师与创业：四篇14章，含工作簿与综合实战](docs/product-founder-book/教材目录.md)
- [产品思维、全栈交付与上线推广实操](docs/product-founder-book/附录D-产品思维训练营.md)
- [架构实验与评审实操](docs/architecture-book/附录D-架构实验与评审实操.md)
- [教材导读：章节结构、运行方法与学习验收](docs/python-book/00-导读与学习方法.md)
- [知识覆盖与阅读层次](docs/python-book/附录A-知识覆盖与阅读层次.md)
- [语言练习任务索引：P01–P60](docs/python-book/附录B-语言练习任务索引.md)
- [Python 能力检查表与阶段验收](docs/python-book/附录C-Python能力检查表.md)
- [学习记录模板](docs/python-book/附录D-学习记录模板.md)

## 配套案例与后续项目

- [订单、HTTP、服务与Agent起始练习及验收命令](practice/python_ai_course/练习说明.md)
- [DocPilot / ProcureAgent虚构数据说明](practice/enterprise_ai/虚构数据说明.md)
- [项目里程碑与交付检查](docs/python-book/附录E-项目里程碑与交付检查.md)
- [项目实践规格：接口、工具、状态与审批](docs/project-practice/项目实践规格.md)
- [项目评测与故障演练](docs/project-practice/评测与故障演练.md)

各套教材按自身前置关系学习，学习导航说明衔接方式；附录用于验收，项目规格用于实现细节。

## 每天怎样学习

先在教材导读中看[学习方法与实操位置](docs/python-book/00-导读与学习方法.md#先看哪里代码写在哪里)。采用“读一个小节→预测运行→修改条件→独立练习→检查验收→记录复习”的流程。

- 小型语法与原理实验放在[章节实验区](practice/chapter_labs/练习说明.md)。
- 配套TODO写在practice/python_ai_course；已完成的业务函数从src复用。
- 正式项目实现放在src/python_agent_lab，测试放在tests。
- 所有命令从本仓库根目录执行；先确认检查导入的是哪份实现。

## 常用命令

```powershell
# 运行订单集合练习
uv run python -m python_agent_lab.basics.collections

# 检查架构、产品教材及配套实验
.venv\Scripts\python.exe -X utf8 scripts\verify_learning_tracks.py

# 运行项目测试
uv run pytest
```
