# 第07章　模块、文件、序列化与命令行

[上一章](06-object-model.md) · [全书目录](README.md) · [下一章](08-standard-library.md)

## 1. 学习目标与前置知识

组织可导入模块，处理外部文本，并提供稳定 CLI。前置：第3–6章。

## 2. 基础知识讲解

模块导入会执行顶层代码并参与缓存。包、绝对/相对导入、-m 运行和工作目录需要分清。将业务计算与文件读取、网络和启动入口分离，减少导入副作用与循环依赖。

文件分文本与二进制模式；Path 表达路径，编码显式选择。JSON/CSV 是外部格式，解析后仍需验证字段、类型和业务规则。时间、金额、元组等往返时必须说明转换契约。

argparse 定义 CLI；stdout 交付正常结果，stderr 说明错误，退出码表达执行状态。写文件需考虑失败时是否保留原内容，需要原子替换时再定义临时文件策略。

## 3. 原理讲解与推导

把模块缓存、名称绑定、文件资源与格式边界联系起来。源码目录能 import 与安装包可用是两个验证目标。

### 17. import 为什么通常只执行一次：模块对象与缓存

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

### 19. 序列化为什么会丢语义：格式只表达有限类型

【库约定】JSON 表达对象、数组、字符串、数值、布尔与 null，没有 Python tuple、datetime 或 Decimal 的完整类型语义。编解码成功不保证业务对象往返仍相同，必须定义数据模型和转换规则。

```python
# experiment: E19
import json
from datetime import datetime
original = (1, 2)
restored = json.loads(json.dumps(original))
assert restored == [1, 2] and type(restored) is list
assert json.loads('{"id": 1, "id": 2}') == {"id": 2}
try:
    json.dumps(float("nan"), allow_nan=False)
except ValueError:
    pass
else:
    raise AssertionError("严格写出时拒绝非有限数")
left = datetime.fromisoformat("2026-11-04T10:00:00+08:00")
right = datetime.fromisoformat("2026-11-04T02:00:00+00:00")
assert left == right
```

Python JSON 的某些默认行为比严格互通格式宽松：例如重复对象键保留后值；默认处理非有限浮点也需注意。要求严格输入时，应选择明确的解析策略与业务校验，不能只看能否 loads。

时间字符串必须保留时区约定；naive 时间不包含足够信息来唯一确定绝对时刻。Decimal 转成字符串后也要保留字段的金额单位/币种契约；default=str 只让错误消失可能反而丢掉约束。

其他标准库的机制也要核对：itertools.groupby 按相邻键分组；heapq 维护堆关系，不是整个列表有序；正则匹配格式不等于业务合法。先写出需要的不变量，再选择工具。

迁移问题：重复键、未知字段、超长记录、无法确定时区的时间，应分别由哪个边界拒绝？

## 4. 示例与逐步走查

```python
# book-example: B07
import json
from pathlib import Path
from tempfile import TemporaryDirectory
with TemporaryDirectory() as folder:
    path = Path(folder) / "sample.json"
    path.write_text(json.dumps({"user":"甲"}, ensure_ascii=False), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == {"user":"甲"}
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

完成订单 CLI，支持输入/输出路径，制造不存在文件、坏 JSON、错误字段、CSV 内含逗号等情况。

### L15：文件与异常分类（P28）

实现文件入口：不存在保留 FileNotFoundError；坏 JSON 保留 JSONDecodeError；语法合法但字段错误抛业务 ValueError。CLI 捕获预期错误输出 stderr 并非零退出，正常结果写 stdout。

验收：三个错误能分别测试；错误记录有文件/位置信息，不能统一返回 []。每个测试使用自己的 tmp_path。

### L16：CSV 与序列化往返（P29）

把包含中文、逗号、引号的用户名称及整数分导出 CSV，再读入校验。使用 csv 模块；金额读取后显式转换与校验，拒绝坏行。

验收：写入再读取的业务记录相等，不能手工 split(',') 破坏带逗号的字段。datetime/Money 导出 JSON 时定义字段格式，不靠 default=str 模糊化所有类型。

## 6. 验收与自测

**行为验收：** 换目录和输入文件无需改业务逻辑；导入模块无自动读取；错误类型和退出码明确。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

import 为什么通常不会重复执行？from import 为什么不自动同步重新赋值？JSON 合法为何不代表订单合法？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](06-object-model.md) · [下一章](08-standard-library.md)
