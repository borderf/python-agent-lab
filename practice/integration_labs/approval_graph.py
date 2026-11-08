"""Persist a real LangGraph interrupt, then resume it in another process."""

import argparse
from contextlib import closing
import json
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from practice.architecture_labs.idempotency_sqlite import apply_local, connect


class State(TypedDict, total=False):
    task_id: str
    tenant: str
    version: int
    decision: str
    result_id: str
    status: str


def approval(state: State):
    response = interrupt({"task_id": state["task_id"], "version": state["version"],
                          "question": "批准此版本的模拟报告吗？"})
    if not isinstance(response, dict) or set(response) != {"decision", "version"}:
        raise ValueError("Invalid approval response")
    if type(response["version"]) is not int or response["version"] != state["version"]:
        raise ValueError("Approval version changed")
    if response["decision"] not in {"approve", "reject"}:
        raise ValueError("Unknown approval decision")
    return {"decision": response["decision"]}


def run(folder: Path, task: str, tenant: str, decision: str | None = None,
        version: int = 1, fail_after_write: bool = False) -> dict:
    if type(version) is not int or version < 1 or not task or not tenant:
        raise ValueError("Task, tenant, and a positive version are required")
    folder.mkdir(parents=True, exist_ok=True)
    config = {"configurable": {"thread_id": json.dumps([tenant, task], ensure_ascii=False)}}
    with SqliteSaver.from_conn_string(str(folder / "checkpoints.sqlite")) as saver:
        def submit(state):
            if state["decision"] == "reject":
                return {"status": "rejected"}
            with closing(connect(folder / "mock-remote.sqlite")) as remote:
                key = f"{state['task_id']}:v{state['version']}"
                receipt = apply_local(remote, state["tenant"], key, {"version": state["version"]})
            if fail_after_write:
                raise RuntimeError("Injected interruption after remote commit")
            return {"status": "completed", "result_id": receipt}

        builder = StateGraph(State)
        builder.add_node("approval", approval)
        builder.add_node("submit", submit)
        builder.add_edge(START, "approval")
        builder.add_edge("approval", "submit")
        builder.add_edge("submit", END)
        graph = builder.compile(checkpointer=saver)
        snapshot = graph.get_state(config)
        if decision:
            if not snapshot.values:
                raise ValueError("Task not found in this tenant")
            if snapshot.interrupts:
                # Reject before the graph persists a resume value that a retry cannot replace.
                if version != snapshot.values["version"]:
                    raise ValueError("Approval version changed")
                if decision not in {"approve", "reject"}:
                    raise ValueError("Unknown approval decision")
                value = Command(resume={"decision": decision, "version": version})
            elif snapshot.next:
                if decision != snapshot.values.get("decision") or version != snapshot.values["version"]:
                    raise ValueError("Resume must preserve the approved decision and version")
                value = None
            else:
                if decision != snapshot.values.get("decision") or version != snapshot.values["version"]:
                    raise ValueError("Completed task preserves its original decision and version")
                return dict(snapshot.values)
        else:
            if snapshot.values:
                raise ValueError("Task already exists; resume it with its original identity")
            value = {"task_id": task, "tenant": tenant, "version": version, "status": "needs_approval"}
        graph.invoke(value, config)
        return dict(graph.get_state(config).values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "resume"))
    parser.add_argument("--folder", type=Path, default=Path(".learning-labs/approval"))
    parser.add_argument("--task", default="T1")
    parser.add_argument("--tenant", default="tenant-a", help="trusted fixture identity, not authentication")
    parser.add_argument("--decision", choices=("approve", "reject"))
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--fail-after-write", action="store_true")
    args = parser.parse_args()
    if (args.action == "resume") != bool(args.decision):
        parser.error("resume requires --decision; prepare omits it")
    result = run(args.folder, args.task, args.tenant, args.decision, args.version, args.fail_after_write)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
