from decimal import Decimal, ROUND_HALF_UP
import math

def example_01():
    assert 0.1 + 0.2 != 0.3
    exact = Decimal("0.1") + Decimal("0.2")
    assert exact == Decimal("0.3")
    rounded = Decimal("1.005").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert rounded == Decimal("1.01")

def example_02():
    assert (-7 // 3, -7 % 3) == (-3, 2)
    assert math.isclose(0.1 + 0.2, 0.3)
    cents = 19901
    yuan, remainder = divmod(cents, 100)
    print(f"{cents} 分 = {yuan} 元 {remainder} 分")

if __name__ == "__main__":
    example_01()
    example_02()