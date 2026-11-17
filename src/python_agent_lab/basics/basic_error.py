def example_else():
    events = []
    try:
        number = int("bad")
    except ValueError:
        events.append("invalid")
    else:
        events.append("valid")
    finally:
        events.append("finished")

    assert events == ["invalid", "finished"]

from  io import StringIO
def example_close():
    first = StringIO("10\n")
    try:
        assert first.readline().strip() == "10"
    finally:
        first.close()
    assert first.closed

    second = StringIO("10\n")
    with second as source:
        assert source.readline().strip() == "10"
    assert second.closed

if __name__ == "__main__":
    # example_else()
    example_close()