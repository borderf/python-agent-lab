# python-agent-lab

一个以项目练习为主的 Python 学习仓库，记录从 Java 后端开发到 AI 应用开发的学习过程。

## 当前进度

当前阶段：Python 基础与集合操作。现有练习围绕订单筛选、统计、分组、排序和去重。

## 当前学习入口

- [教材总目录：Python、项目工程与 AI 开发，五卷30章](docs/python-book/README.md)
- [教材导读：章节结构、运行方法与学习验收](docs/python-book/00-guide.md)
- [配套日程：系统掌握 Python，12 个主题周 / 60 次任务](docs/learning-plan/python-systematic.md)
- [Python 能力检查表与阶段验收](docs/learning-plan/python-competencies.md)

## 配套案例与后续项目

- [原理索引：内容已嵌入教材对应章](docs/python-principles/README.md)
- [专项练习索引：内容已嵌入教材对应章](docs/tutorial/python-language-labs.md)
- [后续 AI 项目：Python 验收后从 W04 继续](docs/learning-plan/enterprise-ai-16-weeks.md)
- [项目实践规格：接口、工具、状态与审批](docs/project-practice/projects.md)
- [历史快速衔接日程：Python → AI Agent，8 周](docs/learning-plan/study-process.md)
- [Python → AI 应用：20 课可练习教程](docs/tutorial/README.md)
- [后续学习路线：从订单分析到 AI 应用](docs/learning-plan/roadmap.md)
- [第一周：Python 集合操作与订单分析](docs/learning-plan/week-01.md)

## 常用命令

```powershell
# 运行订单集合练习
uv run python -m python_agent_lab.basics.collections

# 运行项目测试
uv run pytest
```
