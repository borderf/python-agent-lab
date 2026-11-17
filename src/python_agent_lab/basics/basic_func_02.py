from functools import partial

def example_lambda():
    rows = [{"id": "B", "cents": 200}, {"id": "A", "cents": 100}]

    def amount_key(row):
        return row["cents"]

    assert amount_key(rows[0]) == 200
    by_function = sorted(rows, key=amount_key)
    by_lambda = sorted(rows, key=lambda row: row["cents"])
    assert by_function == by_lambda
    assert [row["id"] for row in by_lambda] == ["A", "B"]
    assert rows[0]["id"] == "B"

def example_partial():
    rows = [{"id": "B", "amount_cents": 10}, {"id": "A", "amount_cents": 10}, {"id": "C", "amount_cents": 5}]
    ordered = sorted(rows, key=lambda row: (row["amount_cents"], row["id"]))
    assert [row["id"] for row in ordered] == ["C", "A", "B"]

    def multiply(value, factor):
        return value * factor
    
    double = partial(multiply, factor=2)
    assert double(7) == 14

if __name__ == "__main__":
    # example_lambda()
    example_partial()