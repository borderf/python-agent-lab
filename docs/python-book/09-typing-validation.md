# 第09章　类型系统、校验模型与接口契约

[上一章](08-standard-library.md) · [全书目录](README.md) · [下一章](10-testing-tools.md)

## 1. 学习目标与前置知识

分清静态描述、运行时校验与业务不变量。前置：第4、6–8章。

## 2. 基础知识讲解

注解表达预期类型，静态检查器据此诊断；运行时普通调用不会自动执行这些检查。TypedDict 描述字典形状，dataclass 描述对象结构，Pydantic 执行额外解析和验证，各有职责。

Union/None、Literal、Callable、Mapping/Sequence 表达返回与依赖范围。object 需要缩窄后使用；Any 放宽检查。TypeVar/泛型保持类型间关系，Protocol 描述结构化接口。

输入校验决定允许转换还是严格拒绝，并检查范围、额外字段、状态和缺失值。格式通过仍需确定性规则、权限与事实校验。

## 3. 原理讲解与推导

类型是契约的一部分；结构相同不保证错误、资源、顺序和副作用语义相同。以可替换实现的行为测试补充静态检查。

### 18. 类型为什么不会阻止坏数据：描述与执行分工

【语言/库约定】注解提供类型信息，运行时通常不替你检查调用。TypedDict 描述字典形状，运行时仍是普通 dict。Protocol 描述支持哪些操作，不保证实现的业务语义、权限和性能。

```python
# experiment: E18
from typing import TypedDict
def echo(value: int) -> int:
    return value
assert echo("text") == "text"  # type: ignore[arg-type]
class Record(TypedDict):
    count: int
record = Record(count="wrong")  # type: ignore[typeddict-item]
assert type(record) is dict and record["count"] == "wrong"
assert echo.__annotations__["return"] is int
```

这个实验应触发静态检查工具的相应诊断；为了展示运行时行为才有意写出错误输入。正确工程仍要修复类型错误，并在外部边界做运行时验证。

Generic 保留不同实例类型之间的关系；Any 放宽检查，object 需要先缩窄。Pydantic 等执行额外的解析/验证，严格模式与默认转换也不同；格式通过不代表金额、权限或引用事实正确。

迁移问题：两个仓储都满足 get(id) 的 Protocol，但其中一个把未知 ID 返回为零金额而不是 None，会破坏什么契约？


## 4. 示例与逐步走查

```python
# book-example: B09
from typing import Protocol
class Names(Protocol):
    def get(self, key: str) -> str | None: ...
class MemoryNames:
    def get(self, key: str) -> str | None:
        return {"A":"Alice"}.get(key)
def lookup(source: Names, key: str) -> str | None:
    return source.get(key)
assert lookup(MemoryNames(), "A") == "Alice"
assert lookup(MemoryNames(), "missing") is None
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成仓储 Protocol、一个实际泛型复用点及严格 OrderModel；对 bool/字符串金额和额外字段写测试。

### L19：可替换仓储与泛型（P38）

定义按 ID 获取订单的 Protocol；内存和文件实现遵守相同契约，未知 ID 返回 None。再用 TypeVar 或 3.12 类型参数语法表达一个真实需要的通用结果容器。

验收：业务函数只依赖契约即可切换实现；静态检查能发现错误返回类型。说明 runtime_checkable 或类型标注不会替你验证所有字段与业务语义。

## 6. 验收与自测

**行为验收：** 静态检查与运行时测试分别记录；未知结果与零值区分；不靠 Any 消除所有诊断。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

Protocol 与继承接口有何区别？TypedDict 会验证 JSON 吗？类型正确为何仍可能破坏业务规则？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](08-standard-library.md) · [下一章](10-testing-tools.md)
