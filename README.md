# python-agent-lab

从 Java 后端转向 Python、AI 应用与 Agent 开发的项目练习仓库。先用 Python 独立交付一个订单工具，再完成两份可单独演示的作品：能引用制度原文的 DocPilot，以及能暂停审批、重启恢复的 ProcureAgent。

**从[学习导航](docs/学习导航.md)开始。** 里面有起点自测、五个阶段的时间预算、章节和交付标准。架构练习、用户访谈与试点都跟随同一组项目进行。

手机阅读版使用 VitePress 构建，包含教材目录、中文搜索和架构图。首次发布与本地预览见[文档网站使用说明](docs/文档网站使用说明.md)。

## 第一次开始

在终端用 `uv --version` 确认工具可用。首次使用时可按系统选择安装方式。[uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)

从仓库根目录执行下列命令，按锁文件准备项目的 Python 3.12 环境：

```powershell
uv sync --locked --inexact
uv run python -X utf8 -m practice.python_ai_course.preflight
uv run python -m pytest practice/python_ai_course/checks_week01.py -q -k "name or format"
```

最后一条检查起始代码已经接通的名称清理与金额展示。第一次自己动手时，打开[整数分迁移练习](practice/python_ai_course/练习说明.md#从旧订单迁移到整数分)，只实现 [week01_orders.py](practice/python_ai_course/week01_orders.py) 的 `total_amount_cents`，用下面的命令验证空输入、按状态汇总和换一组金额：

```powershell
uv run python -m pytest practice/python_ai_course/checks_week01.py -q -k "money_total or money_not_hardcoded"
```

起始代码在这里抛出 `NotImplementedError`，实现后应通过。同一批订单随后会用于去重、报告、HTTP 接口和只读工具。

## 需要时打开

| 当前任务 | 入口 |
| --- | --- |
| 找章节、决定下一步 | [学习导航](docs/学习导航.md) · [Python 与 AI](docs/python-book/教材目录.md) · [软件架构](docs/architecture-book/教材目录.md) · [产品与创业](docs/product-founder-book/教材目录.md) |
| 练语言、找代码位置 | [语言检查表](docs/python-book/附录C-Python能力检查表.md) · [章节实验区](practice/chapter_labs/练习说明.md) · [配套练习及检查文件](practice/python_ai_course/练习说明.md) |
| 实现两份 AI 作品 | [虚构数据与可运行实验](practice/enterprise_ai/虚构数据说明.md) · [接口、工具与审批规格](docs/project-practice/项目实践规格.md) |
| 验收与复盘 | [项目里程碑](docs/python-book/附录E-项目里程碑与交付检查.md) · [评测与故障演练](docs/project-practice/评测与故障演练.md) · [学习记录模板](docs/python-book/附录D-学习记录模板.md) |

## 常用命令

```powershell
# 运行已有的订单集合示例
uv run python -m python_agent_lab.basics.collections

# 验证已实现的仓库代码；配套 TODO 用上面的显式路径检查
uv run pytest

# 检查教材结构、本地链接和配套实验
uv run python -X utf8 scripts/verify_learning_tracks.py
```
