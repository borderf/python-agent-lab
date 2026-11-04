# 第02章　数字、金额、文本与编码

[上一章](01-execution-objects.md) · [全书目录](README.md) · [下一章](03-collections.md)

## 1. 学习目标与前置知识

理解数值表示与文本边界，能实现明确规则的金额转换。前置：第1章。

## 2. 基础知识讲解

int 表示整数，float 表示有限精度浮点数，bool 与 int 存在继承关系。`/` 是真除法，`//` 向下取整，`%` 与整除共同满足商余关系。round、格式化和精确金额计算分别解决不同问题。

固定两位货币可用整数分保存；外部十进制文本需要先定义符号、小数位、币种和舍入规则。Decimal 应从字符串等精确来源构造，运算仍受到上下文精度与舍入影响。

str 是 Unicode 文本，bytes 是字节。strip/split/join 处理字符串，encode/decode 处理编码边界。f-string 的宽度、补零和小数位控制显示，不修复存储误差。码点数量、用户看到的字形数量和 UTF-8 字节数不必相同。

## 3. 原理讲解与推导

先明确“表示了什么”和“采用什么单位”，再进行计算。对不可精确表示的值采用适合业务的表示与比较；输入格式与内部表示分开设计。

### 4. 为什么格式化不修复浮点数：表示与计算

【数值表示】有限二进制浮点数不能精确表示大多数十进制小数。格式化仅改变显示。整数分能精确表达本题限定的最小货币单位；Decimal 使用十进制表示，但其运算也受到精度与舍入上下文限制。

```python
# experiment: E04
from decimal import Decimal
assert 0.1 + 0.2 != 0.3
assert f"{0.1 + 0.2:.2f}" == "0.30"
assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
assert Decimal(0.1) != Decimal("0.1")
assert 1999 + 1 == 2000
assert divmod(2000, 100) == (20, 0)
q, r = divmod(-7, 3)
assert (q, r) == (-3, 2)
assert -7 == q * 3 + r
```

// 的整数结果遵循向下取整，不是向零截断。金额分摊/折扣仍需定义舍入和余数分配规则；改用整数不会自动回答这些业务问题。

应用：先验证金额文本格式，再精确转分；不要 `int(float(text) * 100)`。比较测量误差可使用合理的 isclose 容差，订单金额规则则采用明确单位与精确表示。

迁移问题：100 分均分三人时，如何分配剩余 1 分并保证总额守恒？

### 5. 为什么字符数不等于字节数：Unicode 与编码

【语言/库约定】str 是 Unicode 文本，bytes 是字节序列。encode/decode 在文本与指定编码的字节之间转换。Python 的 str 长度统计码点，不保证等于人看到的字形数量；组合字符和 emoji 会带来差异。

```python
# experiment: E05
import unicodedata
text = "采购A"
raw = text.encode("utf-8")
assert len(text) == 3 and len(raw) == 7
assert raw.decode("utf-8") == text
composed = "\u00e9"
decomposed = "e\u0301"
assert len(composed) == 1 and len(decomposed) == 2
assert composed != decomposed
assert unicodedata.normalize("NFC", decomposed) == composed
try:
    raw[:1].decode("utf-8")
except UnicodeDecodeError:
    pass
else:
    raise AssertionError("截断的 UTF-8 字节不能正常解码")
```

误区：一个字固定占几个字节；用 errors='ignore' 把编码问题静默删除；按字节截断再直接解码。是否做 Unicode 规范化是业务决定，不能默默改变标识符的含义。

迁移问题：文件上传的字节大小限制，与用户名称字符长度限制，为什么需要两个检查？

## 4. 示例与逐步走查

```python
# book-example: B02
def display_cents(cents):
    if type(cents) is not int or cents < 0:
        raise ValueError("需要非负整数分")
    yuan, fen = divmod(cents, 100)
    return f"{yuan}.{fen:02d}"
assert display_cents(1) == "0.01"
assert display_cents(12345) == "123.45"
```

阅读时先预测输入、输出、异常、副作用和资源状态，再执行；修改一处条件验证自己的解释。独立示例有标记，框架片段和项目流程另按依赖/服务条件验证。

## 5. 动手练习

沿用 basic_operation.py 已有 format_cents；补零金额、1分、bool、负数和错误类型。金额解析与中文字节往返按专项题完成。

### L03：文本与字节（P05）

把字符串“采购A”按 UTF-8 编码，再解码，结果相等；分别记录字符数与字节数。将 bytes 写入二进制文件，按相同编码读回；使用错误编码时报告具体异常。

验收：文本“采购A”长度是 3，UTF-8 字节长度是 7。明确字节切片可能截断字符，不能把 bytes 与 str 混接。

### L04：金额解析（P04）

实现 parse_amount_text(text)：去两端空白，仅接受 ASCII 数字组成的非负整数或带 1–2 位小数的金额，返回整数分。用字符串处理或 Decimal 从字符串创建，不经过 float。

验收：`"19"→1900`、`"19.9"→1990`、`"19.99"→1999`、`" 0.01 "→1`；`"19.999"`、`"-1"`、`"NaN"`、`"1e2"`、空串与非字符串均 ValueError。规则选择是本题约定，不是所有金额系统通用解析规则。

## 6. 验收与自测

**行为验收：** 金额合计守恒；编码往返一致；严格拒绝不支持的金额格式；解释格式化与精度的差别。

**原理验收：** 合上资料解释本章一个机制，预测一个反例，说明规则属于语言语义、库约定还是实现观察。

**提交证据：** 实现位置、运行命令、正常案例、至少一个错误/边界案例、一次失败原因和修复记录。自动检查只证明其覆盖行为；未实现任务不因示例通过而算完成。

## 7. 面试问答与迁移

为什么 0.1+0.2 不精确？整数分不能自动解决哪些分摊问题？str/bytes 混用为何出错？

回答顺序：定义与边界 → 机制 → 小例子 → 项目影响 → 验证方式。不确定的实现细节明确说明版本和查证办法。

## 8. 本章小结与参考

先达到行为与原理两类验收，再继续后续依赖本章的任务。遇到不熟悉的内容回到例子做小实验，不以阅读完成代替掌握。

官方参考：[本章资料](https://docs.python.org/zh-cn/3.12/tutorial/)。动态框架资料以2026-11-04核对的入口为准，具体SDK版本在实际实践时重新核对并记录锁文件。

[上一章](01-execution-objects.md) · [下一章](03-collections.md)
