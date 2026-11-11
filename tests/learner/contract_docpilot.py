"""20 progressive behavioral contracts, independent of the reference imports."""
from copy import deepcopy

import pytest


def document(**overrides):
    return {"source_id": "policy-a", "tenant_id": "a", "version": "1", "title": "预付款制度",
            "text": "预付款比例不得超过20%。", "valid_from": "2026-07-01", "valid_to": None, **overrides}


def quote_first(question, evidence):
    return {"answer": evidence[0]["text"], "citations": [
        {"chunk_id": evidence[0]["chunk_id"], "quote": evidence[0]["text"]}], "needs_review": True}


def query(module, index, **overrides):
    return module.search(index, "预付款", **{"tenant_id": "a", "as_of": "2026-07-01", **overrides})


def ask(module, index, model=quote_first, **overrides):
    return module.answer(index, "预付款", **{"tenant_id": "a", "as_of": "2026-07-01", "model": model, **overrides})


def test_s01_document_validation(implementation):
    raw = document(text="  预付款20%  ")
    original = deepcopy(raw)
    assert implementation.normalize_document(raw)["text"] == "预付款20%"
    assert raw == original
    for field in ("source_id", "tenant_id", "text"):
        with pytest.raises(ValueError):
            implementation.normalize_document(document(**{field: " "}))


def test_s02_validity_interval(implementation):
    for fields in ({"valid_from": "not-a-date"}, {"valid_to": "2026-07-01"}, {"valid_from": "2026-02-30"}):
        with pytest.raises(ValueError):
            implementation.normalize_document(document(**fields))


def test_s03_index_has_identity(implementation):
    chunks = implementation.build_index([document()])
    assert len(chunks) == 1
    assert {key: chunks[0][key] for key in ("source_id", "tenant_id", "version")} == {
        "source_id": "policy-a", "tenant_id": "a", "version": "1"}
    assert isinstance(chunks[0]["chunk_id"], str) and chunks[0]["chunk_id"]


def test_s04_chunk_offsets(implementation):
    text = "甲乙丙丁戊己庚"
    chunks = implementation.build_index([document(text=text)], chunk_chars=3)
    assert [chunk["text"] for chunk in chunks] == ["甲乙丙", "丁戊己", "庚"]
    assert all(text[c["start"]:c["end"]] == c["text"] for c in chunks)


def test_s05_chunk_ids_and_input(implementation):
    raw = [document()]
    before = deepcopy(raw)
    first = implementation.build_index(raw, chunk_chars=4)
    assert first == implementation.build_index(raw, chunk_chars=4) and raw == before
    assert len({c["chunk_id"] for c in first}) == len(first)
    for bad in (0, -1, True):
        with pytest.raises(ValueError):
            implementation.build_index(raw, chunk_chars=bad)


def test_s06_duplicate_and_conflict(implementation):
    assert implementation.build_index([document(), document()]) == implementation.build_index([document()])
    with pytest.raises(ValueError):
        implementation.build_index([document(), document(text="预付款30%")])
    assert len(implementation.build_index([document(), document(tenant_id="b")])) == 2


def test_s07_filter_tenant_before_top_k(implementation):
    index = implementation.build_index([document(source_id="b-secret", tenant_id="b"), document()])
    assert [c["source_id"] for c in query(implementation, index, limit=1)] == ["policy-a"]


def test_s08_half_open_dates(implementation):
    index = implementation.build_index([document(source_id="old", valid_from="2026-01-01", valid_to="2026-07-01"),
                                        document(source_id="new")])
    assert [c["source_id"] for c in query(implementation, index)] == ["new"]
    assert [c["source_id"] for c in query(implementation, index, as_of="2026-06-30")] == ["old"]


def test_s09_rank_by_overlap(implementation):
    index = implementation.build_index([document(source_id="low", title="付款", text="付款"),
                                        document(source_id="high", title="预付款", text="预付款")])
    assert [c["source_id"] for c in query(implementation, index)] == ["high", "low"]


def test_s10_limit_validation(implementation):
    index = implementation.build_index([document(source_id=str(i)) for i in range(5)])
    assert len(query(implementation, index, limit=2)) == 2
    for bad in (0, 11, True, "2"):
        with pytest.raises(ValueError):
            query(implementation, index, limit=bad)


def test_s11_no_match_is_empty(implementation):
    assert query(implementation, implementation.build_index([document(title="天气", text="明日晴朗")])) == []


def test_s12_stable_ties_and_no_alias(implementation):
    index = implementation.build_index([document(source_id="z"), document(source_id="a")])
    before = deepcopy(index)
    found = query(implementation, list(reversed(index)))
    assert [c["source_id"] for c in found] == ["a", "z"]
    found[0]["text"] = "changed"
    assert index == before


def test_s13_only_visible_evidence_reaches_model(implementation):
    calls = []
    def model(question, evidence):
        calls.append(evidence)
        return quote_first(question, evidence)
    index = implementation.build_index([document(), document(tenant_id="b", text="预付款秘密")])
    result = ask(implementation, index, model)
    assert len(calls) == 1 and {c["tenant_id"] for c in calls[0]} == {"a"}
    assert result["citations"][0]["source_id"] == "policy-a"


def test_s14_no_evidence_does_not_call_model(implementation):
    def forbidden(*args):
        pytest.fail("无证据时不应调用模型")
    result = ask(implementation, [], forbidden)
    assert result["citations"] == [] and result["needs_review"] is True


def test_s15_output_contract(implementation):
    index = implementation.build_index([document()])
    for bad in ({}, {"answer": "20%", "citations": [], "needs_review": "false"},
                {"answer": "20%", "citations": [], "needs_review": True, "tenant_id": "b"}):
        with pytest.raises(ValueError):
            ask(implementation, index, lambda *args: bad)


def test_s16_citation_must_be_supplied_evidence(implementation):
    with pytest.raises(ValueError):
        ask(implementation, implementation.build_index([document()]), lambda *args: {
            "answer": "20%", "citations": [{"chunk_id": "invented", "quote": "20%"}], "needs_review": False})


def test_s17_quote_must_occur_in_chunk(implementation):
    def model(question, evidence):
        value = quote_first(question, evidence)
        value["citations"][0]["quote"] = "预付款可以超过80%"
        return value
    with pytest.raises(ValueError):
        ask(implementation, implementation.build_index([document()]), model)


def test_s18_duplicate_and_uncited_answers(implementation):
    def duplicated(question, evidence):
        value = quote_first(question, evidence)
        value["citations"] *= 2
        return value
    index = implementation.build_index([document()])
    with pytest.raises(ValueError):
        ask(implementation, index, duplicated)
    with pytest.raises(ValueError):
        ask(implementation, index, lambda *args: {"answer": "20%", "citations": [], "needs_review": False})


def test_s19_model_failure_and_mutation(implementation):
    index = implementation.build_index([document()])
    before = deepcopy(index)
    def timeout(*args):
        raise TimeoutError("injected")
    with pytest.raises(TimeoutError):
        ask(implementation, index, timeout)
    def mutate(question, evidence):
        value = quote_first(question, evidence)
        evidence[0]["text"] = "poison"
        return value
    assert ask(implementation, index, mutate)["citations"][0]["quote"] == document()["text"]
    assert index == before


def test_s20_end_to_end_interleaved_contexts(implementation):
    index = implementation.build_index([
        document(source_id="old", text="预付款30%", valid_from="2026-01-01", valid_to="2026-07-01"),
        document(), document(tenant_id="b", text="预付款80%")])
    for tenant, when, expected in [("a", "2026-06-30", "30%"), ("b", "2026-07-01", "80%"),
                                    ("a", "2026-07-01", "20%"), ("c", "2026-07-01", None)]:
        result = ask(implementation, index, tenant_id=tenant, as_of=when)
        if expected:
            assert expected in result["answer"] and result["citations"]
        else:
            assert result["citations"] == [] and result["needs_review"]
