from functools import wraps

def example_basic():
    events = []
    def record(fn):
        def wrapper(left, right):
            events.append("start")
            result = fn(left, right)
            events.append("success")
            return result
        return wrapper

    def add(left, right):
        return left + right

    add = record(add)
    assert add(2, 3) == 5
    assert events == ["start", "success"]

def example_decorator():
    events = []
    def record(fn):
        @wraps(fn)
        def wrapper(left, right):
            events.append("start")
            result = fn(left, right)
            events.append("success")
            return result
        return wrapper

    @record
    def add(left, right):
        """相加两笔整数金额。"""
        return left + right

    assert add(2, 3) == 5
    assert add.__name__ == "add" and add.__doc__ == "相加两笔整数金额。"
    assert add.__wrapped__(2, 3) == 5
    assert events == ["start", "success"]

if __name__ == "__main__":
    # example_basic()
    example_decorator()
