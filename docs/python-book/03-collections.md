# 第03章　容器、推导式与数据转换

[上一章](02-numbers-text.md) · [全书目录](README.md) · [下一章](04-functions-scope.md)

## 1. 学习目标与前置知识

根据顺序、查找、去重和分组要求选择结构。前置：第1–2章。

## 2. 基础知识讲解

list 适合有序可变序列，tuple 适合固定结构的值序列，dict 适合键值映射，set 适合唯一元素及集合运算。字典保留插入顺序，不是自动排序；集合不提供业务应依赖的原始顺序。

遍历时用 enumerate 获取索引，zip 配对多个序列；需要检查长度一致时明确采用相应检查策略。any/all 会短路，空输入的结果分别为 False/True。推导式用于筛选和转换，复杂状态流程用普通循环更清楚。

sorted 返回新列表，list.sort 原地修改且返回 None。排序 key 提取比较字段，reverse 控制方向；相同 key 的相对顺序保持稳定。Counter/defaultdict/deque 分别解决计数、分组默认值和双端队列问题。

## 3. 原理讲解与推导

哈希与相等共同决定键定位。只保存 ID 的集合不能比较重复记录内容；ID→首条记录的字典能同时维护顺序和冲突检查。复杂度是选择依据之一，还需考虑数据规模、常数和可维护性。

### 6. 字典如何定位键：哈希、相等与顺序

【语义】可哈希对象需要在使用期间保持哈希值稳定，相等对象必须有相等哈希值；反过来，哈希值相同不意味着相等。字典可以区分发生碰撞但不相等的键。

【实现观察】常规 CPython 使用哈希表实现 dict/set，平均查找代价通常优于逐项扫描，但不是所有输入都保证 O(1)。字典插入顺序是语言保证，不是按键排序；set 不提供应依赖的原始插入顺序。

```python
# experiment: E06
class Key:
    def __init__(self, value):
        self.value = value
    def __hash__(self):
        return 1  # 故意碰撞，只用于实验
    def __eq__(self, other):
        if not isinstance(other, Key):
            return NotImplemented
        return self.value == other.value
table = {Key("A"): 10, Key("B"): 20}
assert len(table) == 2 and table[Key("A")] == 10
flags = {True: "first", 1: "second"}
assert len(flags) == 1 and flags[True] == "second"
ordered = {"B": 2, "A": 1}
ordered["B"] = 3
assert list(ordered) == ["B", "A"]
```

误区：哈希值作为跨进程持久标识；tuple 一定可哈希；键对象加入 dict 后可以随意修改影响相等/哈希的字段。覆盖 __eq__ 后应重新考虑 __hash__，不要盲目给可变值对象添加哈希。

应用：用 ID → 首条订单字典实现冲突检查，既保存首见次序，也保留可比较内容。

迁移问题：只用 seen_ids 为什么能去重，却无法知道同 ID 是否金额冲突？


## 4. 示例与逐步走查

```python
# book-example: B03
rows = [{"id":"A","status":"paid"}, {"id":"B","status":"pending"}]
paid = [row["id"] for row in rows if row["status"] == "paid"]
by_status = {}
for row in rows:
    by_status.setdefault(row["status"], []).append(row["id"])
assert paid == ["A"]
assert by_status == {"paid":["A"], "pending":["B"]}
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

实现订单筛选、分组、状态计数、稳定排序和保持首见顺序的冲突去重。先手算已有四笔样例，再更换金额和顺序。

### L05：规范化与输入不变（P06）

对订单记录去掉 id/user 两端空白，保留大小写，金额与状态不改。返回新列表与新订单字典。空 id/user 报错；未知字段按订单规则拒绝。

验收：`{"id":" A ","user":" Alice ","amount_cents":1,"status":"paid"}` 变为 A/Alice，原数据仍保留空白；用 deepcopy 快照检查。

### L06：保持顺序的冲突去重（P08）

复用现有订单样例：完全重复保留第一条；同 ID 任一字段不同抛包含 ID 的 ValueError。保持首见顺序。

验收：ID 为 B/A/B 且 B 两条内容相同，输出 B/A；若第二条 B 金额改变，明确报错。额外测试空输入和输入不变。解释只用 set 保存 ID 为何不足以检查字段冲突。

## 6. 验收与自测

**行为验收：** 同ID完全重复只留一条，字段冲突报错；空输入有定义；原列表和内部字典不被修改。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

字典为什么要求可哈希键？相等与哈希要满足什么关系？稳定排序有什么业务用途？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](02-numbers-text.md) · [下一章](04-functions-scope.md)
