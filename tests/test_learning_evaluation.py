from practice.learning_projects import docpilot_reference as core
from practice.learning_projects.evaluate import evaluate, fixture_quote


DOC = {"source_id": "a", "tenant_id": "a", "version": "1", "title": "付款",
       "text": "预付款20%", "valid_from": "2026-07-01", "valid_to": None}
CASE = {"case_id": "C1", "split": "development", "tenant_id": "a", "as_of": "2026-07-01",
        "question": "预付款", "expected_source_ids": ["a"]}


def test_evaluation_keeps_gold_outside_model():
    received = []
    def model(question, evidence):
        received.append((question, evidence))
        return fixture_quote(question, evidence)
    record, = evaluate(core, [DOC], [CASE], model)
    assert received[0][0] == "预付款"
    assert all("expected_source_ids" not in chunk and "split" not in chunk for chunk in received[0][1])
    assert record["recall_at_3"] == record["reciprocal_rank"] == 1


def test_evaluation_retains_failed_and_unanswerable_cases():
    def timeout(*args):
        raise TimeoutError("injected")
    records = evaluate(core, [DOC], [CASE, {**CASE, "case_id": "C2", "tenant_id": "b", "expected_source_ids": []}], timeout)
    assert len(records) == 2
    assert records[0]["error"] == "TimeoutError"
    assert records[1]["error"] is None and records[1]["recall_at_3"] is None
    assert records[1]["citations"] == [] and records[1]["needs_review"]
