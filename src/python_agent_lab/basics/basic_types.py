def example_01():
    n = 5
    assert (n == 0 or 1) == 1
    assert (n == 0 or n == 1) is False
    assert 0 < n < 10
    assert (10 if n is None else n) == 5

def example_02():
    first = 1000
    second = first
    assert first is second
    first = first + 1
    assert first == 1001
    assert second == 1000
    assert first is not second

def example_03():
    total = 0
    for num in range(2):
        total += num
    assert total == 1
    assert (
        num is not None
    )  # 这个不报错，普通for块不创建独立的局部作用域，因此本例循环后仍可读取num

def example_05():
    text = "订单B"
    for c in text:
        if c == "A":
            found = True
            break
    else:
        found = False
    assert found is False


def example_04():
    assert list(range(4)) == [0, 1, 2, 3]
    assert list(range(2, 7, 2)) == [2, 4, 6]
    assert list(range(3, 0, -1)) == [3, 2, 1]
    assert list(range(3, 0)) == []

def example_06():
    amount_cents = 0
    if amount_cents < 0:
        print("非法金额")
    elif amount_cents == 0:
        print("零金额")
    elif amount_cents < 20000:
        print("未达门槛")
    elif amount_cents >= 20000:
        print("达到门槛")

if __name__ == "__main__":
    example_01()
    example_02()
    example_03()
    example_04()
    example_05()
