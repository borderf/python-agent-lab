"""Implement this adapter around YOUR DocPilot core; copy to learner_persistence.py."""


def put_document(db_path, raw, *, core):
    raise NotImplementedError("steps 1–3: normalize, durable insert, duplicate/conflict")


def search(db_path, question, *, tenant_id, as_of, core):
    raise NotImplementedError("steps 2–5: read committed tenant documents and call core")


def answer(db_path, question, *, tenant_id, as_of, core, model):
    raise NotImplementedError("step 6: reuse the injected core's answer validation")
