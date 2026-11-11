"""Local simulated receiver. Approval comes from a trusted server-side record."""


def payload_hash(payload):
    raise NotImplementedError("先约定规范序列化，再计算摘要")


def submit(db_path, *, tenant_id, action_id, payload, approved_hash, fail_after_commit=False):
    raise NotImplementedError("校验批准，原子保存效果，按稳定键恢复回执")
