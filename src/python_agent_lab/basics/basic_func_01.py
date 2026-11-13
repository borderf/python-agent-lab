def subtotal(cents, /, *, count=1):
    return cents * count

def greet():
    return "你好"

def at_least(minimum):
    def accepts(value):
        return value >= minimum
    return accepts

def make_reader():
    items = []
    def read():
        return items

    def replace(new_items):
        # 声明这不是一个局部变量，赋值要重新绑定最近的、已经存在于外层函数作用域的items
        nonlocal items
        items = new_items
    return read, replace, items


if __name__ == "__main__":
    assert subtotal(100, count=3) == 300

    action = greet
    result = greet()
    assert action() == result
    assert action is greet

    small = at_least(10)
    print(small.__closure__)
    large = at_least(100)
    assert small(20) is True
    assert large(90) is False

    read, replace, original = make_reader()
    print(read.__closure__)
    print(replace.__closure__)
    print(id(original))
    original.append("旧的")
    assert read() == ["旧的"]
    replace(["新的"])
    assert read() == ["新的"]
    assert original == ["旧的"]
