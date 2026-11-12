from copy import deepcopy

def example_01():
    original = [[1], [2]]
    shallow = original.copy()
    assert shallow is not original
    assert original[0] is shallow[0]

    shallow[0].append(9)
    assert original[0] == [1, 9]
    shallow[1] = [8]
    assert original[1] == [2] and shallow[1] == [8]

    # 深拷贝，里面的列表引用也会独立拷贝一份
    deep = deepcopy(original)
    deep[0].append(7)
    assert original[0] == [1, 9]


def example_02():
    # 这个不是创建了 3 个不太的空列表，而是把同一个空列表对象的引用复制了 3 份
    shared = [[]] * 3
    print(shared)
    shared[0].append("A")
    print(shared)

    assert shared[0] is shared[1]
    assert shared[1] is shared[2]

    separate = [[], [], []]
    separate[0].append("A")
    print(separate)

def example_copy():
    ids = ["v1", "appendix", "receipt"]
    primary, *extra = ids
    observer = ids
    ids[:1] = ["v2"]
    assert primary == "v1" and extra == ["appendix", "receipt"]
    assert observer == ["v2", "appendix", "receipt"]

    versions = {"policy": "v1"}
    keys = versions.keys()
    snapshot = list(keys)
    versions["invoice"] = "v2"
    assert list(keys) == ["policy", "invoice"] and snapshot == ["policy"]

def example_sort():
    ids = ["A", "B"]
    amounts = [100, 200]
    # enumerate在保留元素的同时附上序号，start改变起点
    assert list(enumerate(ids, start=1)) == [(1, "A"), (2, "B")]
    # zip按位置配对，默认到较短的来源结束，strict=True要求长度一致，不一致则失败
    assert list(zip(ids, amounts, strict=True)) == [("A", 100), ("B", 200)]
    assert list(zip(ids, [100])) == [("A", 100)]

    assert sum(amounts) == 300
    assert max(amounts) == 200
    assert min(amounts) == 100

    assert sorted(amounts, reverse=True) == [200, 100]
    assert amounts == [100, 200]

    in_place = amounts.copy()
    returned = in_place.sort(reverse=True)
    assert in_place == [200, 100] and returned is None

    # any只需一项为真，空列表时False，all要求全部为真，空列表时True
    assert any([True, False]) is True
    assert all([True, False]) is False
    assert any([]) is False and all([]) is True 

if __name__ == "__main__":
    example_01()
    example_02()
    example_sort()
