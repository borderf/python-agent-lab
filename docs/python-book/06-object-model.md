# 第06章　类、数据模型与协议

[上一章](05-iteration-resources.md) · [全书目录](README.md) · [下一章](07-modules-files.md)

## 1. 学习目标与前置知识

掌握实例状态、值对象、方法绑定和常用协议。前置：第4–5章。

## 2. 基础知识讲解

实例属性保存各对象状态，类属性由类及实例查找共享。普通方法绑定 self，classmethod 绑定类，staticmethod 不自动绑定实例。组合适合替换协作对象，继承适合明确的可替代关系。

dataclass 生成常见样板行为，不自动验证全部类型；field(default_factory=...) 避免共享可变默认状态。frozen 限制普通重新赋值，不递归冻结内部容器。

__repr__/__str__、__len__、__iter__、__contains__ 等协议使自定义对象参与标准操作。属性访问涉及描述器和 MRO；super 沿 MRO 继续查找。只在有需求时深入元类和复杂属性拦截。

## 3. 原理讲解与推导

用绑定方法的实例/函数组成、property 的查找优先级和协作继承顺序解释行为。相等、哈希和可变性要一起设计。

### 13. self 为什么自动传入：函数与绑定方法

【语言协议】存放在类中的普通 Python 函数参与描述器协议。通过实例获取时通常得到绑定方法，里面保存原函数与实例；调用时把实例作为首个参数传入。self 是惯用参数名，不是魔法关键字。

```python
# experiment: E13
class Task:
    def label(self, suffix):
        return self.name + suffix
task = Task()
task.name = "review"
method = task.label
assert method.__self__ is task
assert method.__func__ is Task.label
assert method("!") == Task.label(task, "!") == "review!"
```

staticmethod 不绑定实例，classmethod 绑定访问时相关的类。普通函数对象作为实例属性不自动得到同样的方法绑定；绑定来自属性访问协议。

误区：用 class 保存一个可变 findings 列表，却期待每个实例独立。实例属性应在初始化或 default_factory 中各自建立。

迁移问题：注册的是 task.label 时，注册表实际还间接持有什么对象？这个实例应存活多久？

### 14. property 为何优先：描述器与属性查找

【协议概览】通常实例的默认属性查找会考虑：类/MRO 上的数据描述器、实例字典、非数据描述器或类属性。正常属性查找失败后，若定义了 __getattr__，可进入该后备逻辑。自定义 __getattribute__ 等可以改变过程；类对象和某些特殊方法查找还有其他规则。

property 是数据描述器；没有 setter 的只读 property 也不因此允许同名实例字典条目覆盖它。

```python
# experiment: E14
class Price:
    def __init__(self):
        self._cents = 10
    @property
    def cents(self):
        return self._cents
p = Price()
p.__dict__["cents"] = 999
assert p.cents == 10
try:
    p.cents = 20
except AttributeError:
    pass
else:
    raise AssertionError("只读 property 不能直接赋值")
```

数据描述器通常由类型定义 __set__ 或 __delete__；只有 __get__ 的描述器属于非数据描述器。普通方法相关的函数描述器属于后者，实例属性可以遮蔽它。

应用：让金额、配置等不变量有明确更新入口；property 提供访问约束，不等于对象无法通过任何内部方式修改。不要把 Python 约定式封装误当安全隔离。

迁移问题：在 __getattribute__ 内再直接读 self.x，为什么可能无限递归？

### 15. super 为什么不等于父类：MRO 与协作

【语言语义】super 从当前类在 MRO 中的位置继续查找；它不只是把代码中的某个父类名代入。协作式多继承要求参与方法的签名与调用约定兼容。

```python
# experiment: E15
events = []
class A:
    def run(self):
        events.append("A")
class B(A):
    def run(self):
        events.append("B")
        super().run()
class C(A):
    def run(self):
        events.append("C")
        super().run()
class D(B, C):
    def run(self):
        events.append("D")
        super().run()
D().run()
assert events == ["D", "B", "C", "A"]
assert D.__mro__ == (D, B, C, A, object)
```

调用类创建实例时，常规流程由元类的调用协议组织，__new__ 建立/返回实例，适用时 __init__ 初始化它；__init__ 不是任意创建对象的唯一入口。理解职责后，日常类先使用简单初始化和组合。

误区：显式调用多个父类初始化可以无条件避免问题；写很多 mixin 就是更高级设计。共享祖先可能被重复处理，复杂链也可能打断协作。

迁移问题：仅让 B 不再调用 super，C/A 的处理为什么可能消失？

### 16. dataclass 为什么不自动验证：代码生成与业务约束

【标准库约定】dataclass 为字段生成初始化、表示、比较等常用方法；具体行为由选项决定。类型标注本身不会自动变成业务验证。frozen 限制常规字段重新赋值，不递归冻结所引用的可变对象。

```python
# experiment: E16
from dataclasses import dataclass, field, FrozenInstanceError
@dataclass(frozen=True)
class Settings:
    labels: list[str] = field(default_factory=list)
one, two = Settings(), Settings()
one.labels.append("A")
assert one.labels == ["A"] and two.labels == []
try:
    one.labels = []
except FrozenInstanceError:
    pass
else:
    raise AssertionError("frozen 禁止常规重新赋值")
try:
    hash(one)
except TypeError:
    pass
else:
    raise AssertionError("字段中的 list 仍不可哈希")
```

相等与哈希必须协调。dataclass 的 eq/frozen/unsafe_hash 影响生成规则，不能只为放进 set 就启用 unsafe_hash。金额对象需要自己验证单位、类型、范围和跨币种操作。

迁移问题：一个 frozen 对象仍包含可变列表，是否适合用作可长期依赖的缓存键？

## 4. 示例与逐步走查

```python
# book-example: B06
from dataclasses import dataclass, field
@dataclass
class ReviewJob:
    name: str
    findings: list[str] = field(default_factory=list)
a, b = ReviewJob("A"), ReviewJob("B")
a.findings.append("missing")
assert b.findings == []
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成 Money 值对象和订单集合协议；加入类变量共享反例，观察 MRO 变化。

### L13：Money 值对象（P22）

用 dataclass 定义整数 cents 与 currency。本题币种仅允许 CNY/USD；拒绝负数、bool 和非整数金额；同币种可加，不同币种报 ValueError。明确相等与不可变接口。

验收：CNY 1999 + CNY 1 = CNY 2000；跨币种不加；frozen 对象字段不能直接重新赋值。对非 Money 加法返回 NotImplemented，理解最终 TypeError 的来源。

### L14：集合对象与协议（P23–25）

实现 OrderCollection：len() 得数量，迭代得到订单，`"10001" in collection` 按 ID 判断。构造时明确是否复制，公开接口不得意外暴露内部可变状态。

再做一个小菱形继承实验，打印 __mro__，解释 super 的下一步。验收：功能来自协议与数据设计，不只写很多同名 Java 风格方法。

## 6. 验收与自测

**行为验收：** 实例状态不串联；跨币种操作拒绝；repr 有调试价值；不靠任意 magic method 堆砌功能。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

property 为什么不只是 Getter？super 为什么可能调用到兄弟类？frozen 一定可哈希吗？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](05-iteration-resources.md) · [下一章](07-modules-files.md)
