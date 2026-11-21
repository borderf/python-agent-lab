def example_iter():
    values = iter([10, 20])
    assert iter(values) is values
    assert next(values) == 10
    assert next(values) == 20
    assert next(values, "END") == "END"
    assert list(values) == []


def example_iter_02():
    rows = [10, 20]
    left = iter(rows)
    right = iter(rows)
    assert next(left) == 10
    assert next(right) == 10
    assert next(left) == 20

    alias = right
    assert next(right) == 20
    assert next(right, "END") == "END"
    assert rows == [10, 20]


def example_yield():
    events = []

    def values():
        events.append("start")
        yield 10
        events.append("resume")
        yield 20

    stream = values()
    assert events == []
    assert next(stream) == 10 and events == ["start"]
    assert next(stream) == 20 and events == ["start", "resume"]
    assert list(stream) == []


from contextlib import closing


def example_yield_01():
    events = []

    def stream_values():
        try:
            yield 1
            yield 2
        finally:
            events.append("done")

    with closing(stream_values()) as stream:
        assert next(stream) == 1
    assert events == ["done"]


from contextlib import contextmanager, ExitStack


def example_yield_02():
    events = []

    @contextmanager
    def one_source(name):
        events.append(f"open: {name}")
        try:
            yield name
        finally:
            events.append(f"close: {name}")

    with one_source("A") as source:
        assert source == "A"
        assert events == ["open: A"]
        events.append(f"work: {source}")
    assert events == ["open: A", "work: A", "close: A"]


def example_yield_03():
    events = []

    @contextmanager
    def one_source(name):
        events.append(f"open: {name}")
        try:
            yield name
        finally:
            events.append(f"close: {name}")

    try:
        with one_source("B") as source:
            raise ValueError("内容无效")
    except ValueError as exc:
        assert str(exc) == "内容无效"
        assert events == ["open: B", "close: B"]
    else:
        raise AssertionError("错误应传递到 with 外面")


def example_yield_04():
    events = []

    @contextmanager
    def one_source(name):
        if name == "bad":
            raise OSError("无法打开")
        events.append(f"open: {name}")
        try:
            yield name
        finally:
            events.append(f"close: {name}")

    try:
        with ExitStack() as stack:
            for name in ["A", "B", "bad"]:
                stack.enter_context(one_source(name))
    except OSError as exc:
        assert str(exc) == "无法打开"
        assert events == ["open: A", "open: B", "close: B", "close: A"]
    else:
        raise AssertionError("第三份来源应当打开失败")


if __name__ == "__main__":
    # example_yield_01()
    # example_yield_02()
    # example_yield_03()
    example_yield_04()
