"""Implement in your own copy, then run tests/learner/contract_docpilot.py.

The tutorial in chapter 23 introduces these functions in dependency order.
"""


def normalize_document(raw):
    raise NotImplementedError("步骤 1–2：校验来源、文本、租户与半开生效区间")


def build_index(documents, chunk_chars=120):
    raise NotImplementedError("步骤 3–6：规范化、切块、去重与冲突")


def search(index, question, *, tenant_id, as_of, limit=3):
    raise NotImplementedError("步骤 7–12：先过滤，再排序，最后截断")


def answer(index, question, *, tenant_id, as_of, model):
    raise NotImplementedError("步骤 13–20：证据、模型边界与引用验证")
