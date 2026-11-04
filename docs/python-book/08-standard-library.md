# 第08章　标准库、时间、算法工具与数据库

[上一章](07-modules-files.md) · [全书目录](README.md) · [下一章](09-typing-validation.md)

## 1. 学习目标与前置知识

按数据语义选择标准库，理解时间和事务边界。前置：第3、5、7章。

## 2. 基础知识讲解

Counter、defaultdict、deque 面向计数、默认分组和队列；itertools 组合迭代过程，groupby 按相邻键分组；heapq 保持堆关系，不代表整个列表排好序。工具要符合输入顺序和空间需求。

datetime 的 naive/aware、固定偏移与地区时区不是同一个概念。绝对时间比较要保留足够时区信息；业务日期区间的闭开端点要写进规则。

sqlite3 涉及连接、游标、事务与参数化 SQL。事务作用域与连接生命周期分开；正则检查格式，业务规则检查意义。查文档优于背下整个标准库。

## 3. 原理讲解与推导

先写不变量：金额守恒、时间可比较、批次全成或全败，再选择具体数据结构、格式和事务策略。

### 20. 数据库 with 为什么没关连接：事务与资源是两件事

【sqlite3 约定】连接作为上下文管理器时主要管理已有事务的提交/回滚，不负责自动关闭连接，也不意味着所有语句和所有事务配置行为相同。本例使用 Python 3.12 默认的传统事务控制；改变 autocommit/isolation_level 后要重新核对边界。

```python
# experiment: E20
import sqlite3
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, cents INTEGER)")
    try:
        with connection:
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 10))
            connection.execute("INSERT INTO orders VALUES (?, ?)", ("A", 20))
    except sqlite3.IntegrityError:
        pass
    assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    # with 已退出，但连接仍可使用。
finally:
    connection.close()
try:
    connection.execute("SELECT 1")
except sqlite3.ProgrammingError:
    pass
else:
    raise AssertionError("关闭后不能继续查询")
```

参数化 SQL 把值和语句结构分开，不应使用字符串拼接处理用户值。一个数据库事务也不会自动覆盖另一个 HTTP 服务的写入；跨边界副作用需单独设计幂等、对账和失败恢复。

应用：把连接生命周期、事务范围和业务操作分开写清楚。用临时数据库验证批次失败后是否真的全部回滚。

迁移问题：写入外部服务已经成功、本地记录成功状态前崩溃，单靠重试为什么可能重复操作？

## 4. 示例与逐步走查

```python
# book-example: B08
from collections import Counter
from datetime import datetime
counts = Counter(["paid", "pending", "paid"])
assert counts["paid"] == 2 and counts["missing"] == 0
assert datetime.fromisoformat("2026-11-04T10:00:00+08:00") == datetime.fromisoformat("2026-11-04T02:00:00+00:00")
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成时间区间与 SQLite 批次导入；比较排序和堆的 Top-K 结果，说明并列规则。

### L17：时区与有效区间（P32）

比较两个 aware 时间 `2026-11-04T10:00:00+08:00` 与 `2026-11-04T02:00:00+00:00`，它们代表同一时刻。拒绝在未约定时区时把 naive 时间默认为某个区域。

实现 start <= t < end 的有效区间：起点有效、终点无效。测试 UTC 比较和边界。IANA zoneinfo 数据在环境缺失时需明确安装/提供 tzdata；固定偏移示例可先不依赖它。

### L18：SQLite 与事务（P35）

在临时数据库创建订单表，金额用整数，参数化插入用户 `O'Reilly`，查询结果完整保留名称。批次第二条失败时，按约定让整个批次回滚。

验收：不拼接 SQL 值；失败批次没有半写入；连接明确关闭。理解 sqlite3 连接上下文主要管理事务，不能假定退出上下文就关闭连接。

## 6. 验收与自测

**行为验收：** SQL 值参数化；中途失败回滚；时间端点测试明确；连接关闭；性能结论有规模说明。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

groupby 与 SQL GROUP BY 有什么差异？连接 with 是否等于关闭？Top-K 何时不必全排序？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](07-modules-files.md) · [下一章](09-typing-validation.md)
