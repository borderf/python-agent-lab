def subtotal(cents, /, *, count=1):
    return cents * count

if __name__ == "__main__":
    assert subtotal(100, count=3) == 300