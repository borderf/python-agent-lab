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


if __name__ == "__main__":
    example_yield_01()
