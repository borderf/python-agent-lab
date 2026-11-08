"""Offline contract and regression checks for the course's model-facing labs."""
import io
import json
import sys

import pytest

from practice.enterprise_ai import docpilot_question, ollama_local, policy_agent, vector_compare
from practice.enterprise_ai.retrieval_baseline import DATA, evaluate


def read_fixture(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture
def case():
    return next(row for row in read_fixture("retrieval_cases.json") if row["case_id"] == "historical_limit")


def test_http_tool_loop_replays_real_tool_result(monkeypatch, case):
    requests = []

    def respond(request, timeout):
        assert request.full_url == "http://127.0.0.1:11434/api/chat"
        assert timeout > 0
        body = json.loads(request.data)
        requests.append(body)
        assert body["model"] == "test-model" and body["stream"] is False
        return io.BytesIO(json.dumps(policy_agent.fixture_chat(body)).encode())

    monkeypatch.setattr(ollama_local, "urlopen", respond)
    result = policy_agent.run_case(lambda body: ollama_local.post("/api/chat", body),
                                   "test-model", "brief", case, read_fixture("policies.json"))
    assert [msg["role"] for msg in requests[1]["messages"]] == ["system", "user", "assistant", "tool"]
    assert requests[1]["messages"][-1]["tool_name"] == "get_prepayment_limit"
    assert json.loads(requests[1]["messages"][-1]["content"]) == result["answer"]
    assert result["supported"] and result["answer"] == {"limit_percent": 30, "source_id": "policy-a-old"}


@pytest.mark.parametrize("response", [
    {"done": False},
    {"done": True, "done_reason": "length", "message": {"role": "assistant", "content": "{}"}},
    {"done": True, "message": {"role": "assistant", "tool_calls": [
        {"function": {"name": "get_prepayment_limit", "arguments": {"tenant_id": "tenant-b"}}}]}},
    {"done": True, "message": {"role": "assistant", "tool_calls": [
        {"function": {"name": "write", "arguments": {}}}]}},
])
def test_bad_decision_never_executes_tool(response, case):
    result = policy_agent.run_case(lambda _: response, "test", "brief", case, [])
    assert result["status"] == "failed" and result["trace"] == []


def test_duplicate_tool_fields_rejected_before_dispatch():
    with pytest.raises(ValueError, match="duplicate JSON field: arguments"):
        ollama_local.decode_json('{"function":{"arguments":{"tenant_id":"other"},"arguments":{}}}')


def test_guess_without_lookup_is_unsupported(case):
    response = {"done": True, "message": {"role": "assistant", "content":
                '{"limit_percent":30,"source_id":"policy-a-old"}'}}
    result = policy_agent.run_case(lambda _: response, "test", "brief", case, [])
    assert result["supported"] is False and result["trace"] == []


@pytest.mark.parametrize("embeddings", [[], [[0, 0]], [[1, float("nan")]], [[False, 1]]])
def test_bad_vectors_rejected(monkeypatch, embeddings):
    monkeypatch.setattr(vector_compare, "post", lambda *args: {"embeddings": embeddings})
    with pytest.raises(ValueError):
        vector_compare.unit_vectors(["query"], "embed-test")


def test_all_retrieval_methods_share_visible_candidates(monkeypatch, capsys):
    def respond(path, body):
        if path == "/api/embed":
            assert body["truncate"] is False and body["model"] == "embed-test"
            return {"embeddings": [[len(text), 1.0] for text in body["input"]]}
        assert path == "/api/chat" and body["model"] == "rerank-test"
        candidates = json.loads(body["messages"][-1]["content"])["candidates"]
        assert len(candidates) == 6
        assert "policy-b-current" not in candidates and "untrusted-note-a" not in candidates
        return {"done": True, "message": {"role": "assistant", "content": json.dumps(
            {"ids": list(reversed(candidates))})}}

    monkeypatch.setattr(vector_compare, "post", respond)
    monkeypatch.setattr(sys, "argv", ["vector_compare", "--embed-model", "embed-test",
                                      "--rerank-model", "rerank-test", "--split", "holdout"])
    vector_compare.main()
    output = capsys.readouterr().out
    for method in ["bigram", "dense", "rrf", "rrf+rerank"]:
        assert f"{method}: n=4 " in output


def test_reranker_cannot_invent_candidates(monkeypatch):
    monkeypatch.setattr(vector_compare, "post", lambda *args: {
        "done": True, "message": {"role": "assistant", "content": '{"ids":["unknown"]}'}})
    with pytest.raises(ValueError, match="permutation"):
        vector_compare.rerank("query", ["policy-a-old"], read_fixture("policies.json"), "test")


def test_grounded_question_uses_only_current_evidence(monkeypatch, capsys):
    def respond(path, request):
        assert path == "/api/chat"
        context = json.loads(request["messages"][-1]["content"])["evidence"]
        sources = {item["source_id"]: item["text"] for item in context}
        assert "policy-a-old" not in sources and "policy-b-current" not in sources
        answer = {"answer": "20%", "needs_review": False, "citations": [
            {"source_id": "policy-a-current", "quote": "20%"}]}
        assert "20%" in sources["policy-a-current"]
        return {"done": True, "message": {"role": "assistant", "content": json.dumps(answer)}}

    monkeypatch.setattr(docpilot_question, "post", respond)
    monkeypatch.setattr(sys, "argv", ["docpilot_question", "本租户预付款比例上限是多少？",
                                      "--as-of", "2026-07-01", "--model", "test-chat"])
    docpilot_question.main()
    assert json.loads(capsys.readouterr().out)["answer"] == "20%"


@pytest.mark.parametrize("citations", [
    [], [{"source_id": "other", "quote": "20%"}], [{"source_id": "current", "quote": "30%"}],
])
def test_unsupported_citations_fail_validation(citations):
    content = json.dumps({"answer": "30%", "needs_review": False, "citations": citations})
    with pytest.raises(ValueError):
        docpilot_question.validate_answer(content, {"current": "上限20%"})


def test_missing_relevant_hit_scores_zero_not_an_evaluation_crash(case, capsys):
    evaluate(read_fixture("policies.json"), [case], "shortlist", lambda q, rows: [])
    assert "Recall@5=0.000 MRR@5=0.000" in capsys.readouterr().out
