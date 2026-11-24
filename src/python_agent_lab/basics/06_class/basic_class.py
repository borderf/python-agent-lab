def example_01():
    def add_finding(job, text):
        job["findings"].append(text)

    job_a = {"name": "A", "findings": []}
    job_b = {"name": "B", "findings": []}

    add_finding(job_a, "缺少附件")

    assert job_a["findings"] == ["缺少附件"]
    assert job_b["findings"] == []

def example_02():
    class ReviewJob:
        def __init__(self, name) -> None:
            self.name = name
            self.findings = []

        def add(self, finding):
            self.findings.append(finding)

    a, b = ReviewJob("A"), ReviewJob("B")
    a.add("缺少附件")

    assert a.findings == ["缺少附件"] and b.findings == []
    assert a.findings is not b.findings

def example_03():
    class ReviewJob:
        findings = []
        def __init__(self, name) -> None:
            self.name = name

        def add(self, finding):
            self.findings.append(finding)

    a, b = ReviewJob("A"), ReviewJob("B")
    a.findings.append("aaaa")
    assert b.findings == ["aaaa"]
    

def example_04():
    class Limit:
        def __init__(self, value) -> None:
            if type(value) is not int or value <= 0:
                raise ValueError("limit必须是正整数")
            self._value = value

        @property
        def value(self):
            return self._value

        @classmethod
        def from_text(cls, text):
            return cls(int(text))

    limit = Limit.from_text("3")
    assert limit.value == 3
    try:
        limit.value = 4 # 会报错，不可以直接赋值
    except AttributeError:
        pass
    else:
        raise AssertionError("只读property应拒绝普通赋值")


if __name__ == "__main__":
    # example_01()
    # example_02()
    example_03()
