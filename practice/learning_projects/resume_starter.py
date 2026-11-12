"""Copy to learner_resume.py; implement the six cumulative workflow steps."""


def prepare(db_path, *, tenant_id, task_id, payload):
    raise NotImplementedError("step 1: save version 1 in waiting_approval")


def load(db_path, *, tenant_id, task_id):
    raise NotImplementedError("steps 1–2: tenant-scoped durable state")


def change_payload(db_path, *, tenant_id, task_id, expected_version, payload):
    raise NotImplementedError("step 3: increment version and invalidate approval")


def approve(db_path, *, tenant_id, task_id, expected_version, expected_hash):
    raise NotImplementedError("step 3: bind trusted approval to displayed version and hash")


def resume(db_path, effects_db, *, tenant_id, task_id, expected_version, fail_after_commit=False):
    raise NotImplementedError("steps 4–6: freeze, submit stable key, reconcile and complete")
