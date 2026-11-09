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
    assert total == 0
    assert num is None

if __name__ == "__main__":
    example_01()
    example_02()
    example_03()