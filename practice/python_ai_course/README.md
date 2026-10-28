# 练习区使用说明

先读 [教程入口](../../docs/tutorial/README.md)，再按课次完成 weekXX 模块中的 TODO。所有关键需求都写在函数文档或课程中。NotImplementedError 是留给你的练习位置。

| 课次 | 起始文件 | 手动指定的验收文件 |
| --- | --- | --- |
| 01–05 | week01_orders.py | checks_week01.py |
| 06–10 | week02_clients.py；CLI 自行创建 | checks_week02.py |
| 11–15 | week03_service.py；api.py 自行创建 | checks_week03.py |
| 16–20 | week04_agent.py；真实模型适配器自行创建 | checks_week04.py |

从项目根目录运行：

```powershell
uv run python -X utf8 -m practice.python_ai_course.preflight
uv run python -m pytest practice/python_ai_course/checks_week01.py -q
uv run python -m pytest practice/python_ai_course/checks_week01.py -q -k money
```

第 02–04 阶段分别依赖前面阶段完成的业务函数；因此先修复前一阶段失败。检查文件不叫 test_*.py，默认项目测试不收集它们；指定文件路径即可运行。第二、三周尚未安装可选依赖时，对应检查会显示跳过；跳过不代表学习完成。

data/orders.json 为基础四笔订单；duplicate_orders.json 多一条完全重复记录；conflicting_orders.json 有同 ID 字段冲突；tied_orders.json 用于金额并列。样例均为虚构数据。

自测后仍要自己补案例。不要将需求里的预期数值硬编码进业务函数；修改样例后函数应根据输入重新计算。ScriptedModel 是有意按脚本返回的测试替身，不是真实 AI。
