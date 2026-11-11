"""A two-turn read-only policy lookup with a fixture or a local tool-capable model."""
import argparse
import json
from time import perf_counter

from .ollama_local import assistant_message, decode_json, post
from .retrieval_baseline import DATA, eligible_sources


TOOL = {"type": "function", "function": {
    "name": "get_prepayment_limit", "description": "查询当前任务租户和业务日期适用的预付款上限",
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}}
PROMPTS = {
    "brief": "查询预付款上限，最终只输出含 limit_percent 和 source_id 的 JSON。",
    "grounded": "先调用工具查证当前任务的有效条款，直接采用工具给出的百分数和来源。"
                "最终只输出含 limit_percent 和 source_id 的 JSON。",
}
# This lab covers a single business question with three date conditions.
CASE_IDS = ("current_limit", "historical_limit", "effective_boundary")


def lookup_limit(policies: list[dict], tenant: str, date: str) -> dict:
    rows = [row for row in eligible_sources(policies, tenant, date)
            if "max_prepayment_percent" in row]
    if len(rows) != 1:
        raise ValueError("policy missing or ambiguous")
    row = rows[0]
    return {"limit_percent": row["max_prepayment_percent"], "source_id": row["source_id"]}


def fixture_chat(request: dict) -> dict:
    last = request["messages"][-1]
    if last["role"] == "tool":
        message = {"role": "assistant", "content": last["content"]}
    else:
        message = {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_prepayment_limit", "arguments": {}}}]}
    return {"done": True, "message": message}


def run_case(chat, model, prompt, case, policies) -> dict:
    messages = [{"role": "system", "content": PROMPTS[prompt]},
                {"role": "user", "content": case["query"]}]
    trace = []
    usage = []
    observed = None
    start = perf_counter()
    result = {"status": "failed", "trace": trace, "usage": usage}
    try:
        for step in range(1, 3):
            request = {"model": model, "messages": messages, "stream": False,
                       "tools": [TOOL], "options": {"temperature": 0, "num_predict": 256}}
            response = chat(request)
            usage.append({k: response[k] for k in ("prompt_eval_count", "eval_count") if k in response})
            message = assistant_message(response)
            messages.append(message)
            calls = message.get("tool_calls", [])
            if not isinstance(calls, list):
                raise ValueError("invalid tool call list")
            if calls:
                if len(calls) != 1 or observed is not None or step == 2:
                    raise ValueError("tool budget exceeded")
                call = calls[0]
                fn = call.get("function") if isinstance(call, dict) else None
                if not isinstance(fn, dict) or fn.get("name") != "get_prepayment_limit" or fn.get("arguments") != {}:
                    raise ValueError("unknown tool or invalid arguments")
                observed = lookup_limit(policies, case["tenant_id"], case["as_of"])
                trace.append({"step": step, "tool": fn["name"], "source_id": observed["source_id"]})
                messages.append({"role": "tool", "tool_name": fn["name"],
                                 "content": json.dumps(observed, ensure_ascii=False)})
                continue
            content = message.get("content")
            if not isinstance(content, str):
                raise ValueError("missing final content")
            answer = decode_json(content)
            if not isinstance(answer, dict) or set(answer) != {"limit_percent", "source_id"}:
                raise ValueError("invalid answer fields")
            if type(answer["limit_percent"]) is not int or not isinstance(answer["source_id"], str):
                raise ValueError("invalid answer types")
            result.update(status="completed", answer=answer, supported=answer == observed)
            break
    except (ValueError, RuntimeError) as exc:
        result["error"] = str(exc)
    result["elapsed_ms"] = round((perf_counter() - start) * 1000, 1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="installed Ollama chat model; default uses an offline fixture")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--compare", action="store_true", help="compare two prompts on identical cases")
    args = parser.parse_args()
    if args.model is not None and not args.model.strip():
        parser.error("--model must not be empty; omit it to use the fixture")
    if args.trials < 1:
        parser.error("--trials must be positive")
    policies = json.loads((DATA / "policies.json").read_text(encoding="utf-8"))
    cases = json.loads((DATA / "retrieval_cases.json").read_text(encoding="utf-8"))
    chat = (lambda request: post("/api/chat", request)) if args.model else fixture_chat
    model = args.model or "fixture"
    all_passed = True
    for prompt in (PROMPTS if args.compare else ["grounded"]):
        passed = total = 0
        for case in cases:
            if case["case_id"] not in CASE_IDS:
                continue
            for trial in range(1, args.trials + 1):
                record = run_case(chat, model, prompt, case, policies)
                # Gold labels stay in the grader, never in the model's messages.
                expected_id, = case["expected_source_ids"]
                expected = next(p for p in policies if p["source_id"] == expected_id)
                ok = bool(record.get("supported") and record["answer"] == {
                    "source_id": expected_id, "limit_percent": expected["max_prepayment_percent"]})
                print(json.dumps(dict(case_id=case["case_id"], trial=trial, prompt=prompt,
                                      model=model, passed=ok, **record), ensure_ascii=False))
                passed += ok
                total += 1
        print(json.dumps(dict(prompt=prompt, passes=passed, attempts=total, model=model)))
        all_passed &= passed == total == len(CASE_IDS) * args.trials
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
