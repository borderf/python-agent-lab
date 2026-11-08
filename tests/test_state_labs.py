import json
import sqlite3
import subprocess
import sys

import pytest


def test_langgraph_survives_separate_processes_and_remote_commit_failure(tmp_path):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    folder = tmp_path / "graph"
    command = [sys.executable, "-m", "practice.integration_labs.approval_graph"]
    common = ["--folder", str(folder), "--task", "T1"]
    prepared = subprocess.run(command + ["prepare"] + common, capture_output=True, text=True, timeout=30)
    assert prepared.returncode == 0, prepared.stderr
    assert json.loads(prepared.stdout)["status"] == "needs_approval"
    interrupted = subprocess.run(command + ["resume", "--decision", "approve", "--fail-after-write"] + common,
                                 capture_output=True, text=True, timeout=30)
    assert interrupted.returncode != 0 and "Injected interruption" in interrupted.stderr
    resumed = subprocess.run(command + ["resume", "--decision", "approve"] + common,
                             capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "completed"
    with sqlite3.connect(folder / "mock-remote.sqlite") as db:
        assert db.execute("SELECT count(*) FROM effects").fetchone()[0] == 1


def test_qdrant_lifecycle_reopens_and_repeats(tmp_path):
    pytest.importorskip("qdrant_client")
    from practice.integration_labs.qdrant_lifecycle import run
    run(tmp_path / "vectors")
    run(tmp_path / "vectors")


def test_graph_rejects_wrong_version_and_wrong_identity(tmp_path):
    pytest.importorskip('langgraph.checkpoint.sqlite')
    from practice.integration_labs.approval_graph import run
    run(tmp_path, 'T1', 'a')
    with pytest.raises(ValueError, match='not found'):
        run(tmp_path, 'T1', 'b', 'approve')
    run(tmp_path, 'T2', 'a:b')
    with pytest.raises(ValueError, match='not found'):
        run(tmp_path, 'b:T2', 'a', 'approve')
    with pytest.raises(ValueError, match='version changed'):
        run(tmp_path, 'T1', 'a', 'approve', version=2)
    assert run(tmp_path, 'T1', 'a', 'reject')['status'] == 'rejected'
    with pytest.raises(ValueError, match='original decision'):
        run(tmp_path, 'T1', 'a', 'approve')


def test_bounded_capacity_accounts_for_every_request():
    import asyncio
    from practice.integration_labs.capacity import measure
    result = asyncio.run(measure(0))
    assert result['completed'] + result['rejected'] == result['total'] == 20
    assert result['rejected'] > 0
    assert len({row['id'] for row in result['records']}) == 20


def test_mcp_real_server_process_matches_local_and_rejects_forged_identity():
    pytest.importorskip('mcp')
    result = subprocess.run([sys.executable, '-m', 'practice.integration_labs.mcp_client'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert set(row['tools']) == {'get_prepayment_limit', 'get_policy_source'}
    assert row['result']['limit_percent'] == 20
    assert row['local_equal'] and row['identity_injection_rejected'] and row['other_tenant_hidden']

