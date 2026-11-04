# 原理三：对象模型、导入与类型

[原理入口](README.md) · 对应 P21–27、P36–40

## 13. self 为什么自动传入：函数与绑定方法

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

## 14. property 为何优先：描述器与属性查找

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

## 15. super 为什么不等于父类：MRO 与协作

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

## 16. dataclass 为什么不自动验证：代码生成与业务约束

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

## 17. import 为什么通常只执行一次：模块对象与缓存

【导入机制】正常导入先检查相应模块缓存；首次导入创建并执行模块。模块对象与 `from module import value` 绑定的名称不是持续同步的同一槽位。循环导入可能看到尚未初始化完的模块。

下面只为观察导入机制临时加路径并在 finally 清理，不是建议业务项目依赖临时路径补丁。

```python
# experiment: E17
import importlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
name = "principles_import_demo"
with TemporaryDirectory() as folder:
    Path(folder, name + ".py").write_text("value = 1\n", encoding="utf-8")
    sys.path.insert(0, folder)
    try:
        first = importlib.import_module(name)
        second = importlib.import_module(name)
        assert first is second
        from principles_import_demo import value
        first.value = 2
        assert value == 1 and second.value == 2
    finally:
        sys.path.remove(folder)
        sys.modules.pop(name, None)
```

CPython 的 .pyc 缓存编译产物不等于业务结果缓存，也不意味着模块永远不执行顶层代码。`-m` 按模块运行，__name__、包上下文与直接路径运行的方式有关。将文件读取、网络和启动流程放到明确入口，是控制导入副作用的重要方法。

应用：打包后从非源码目录运行；不要仅凭仓库根目录下能 import，就判断安装包包含全部模块。

迁移问题：若 value 指向列表，导入后修改列表与重新绑定 first.value，观察者会看到什么不同？

## 18. 类型为什么不会阻止坏数据：描述与执行分工

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

依据：[数据模型](https://docs.python.org/3.12/reference/datamodel.html)、[描述器指南](https://docs.python.org/3.12/howto/descriptor.html)、[导入系统](https://docs.python.org/3.12/reference/import.html)、[dataclasses](https://docs.python.org/3.12/library/dataclasses.html)、[typing](https://docs.python.org/3.12/library/typing.html)。
