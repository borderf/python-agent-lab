"""Deterministic checks for the AI foundations companion book."""

from __future__ import annotations

import math
from collections.abc import Sequence


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    scaled = [value / temperature for value in logits]
    maximum = max(scaled)
    exps = [math.exp(value - maximum) for value in scaled]
    total = sum(exps)
    return [value / total for value in exps]


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector dimensions differ")
    return sum(x * y for x, y in zip(a, b))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    denominator = math.sqrt(dot(a, a)) * math.sqrt(dot(b, b))
    if denominator == 0:
        raise ValueError("zero vector has no cosine")
    return dot(a, b) / denominator


def masked_attention(
    query: Sequence[float],
    keys: Sequence[Sequence[float]],
    values: Sequence[Sequence[float]],
    query_index: int,
) -> tuple[list[float], list[float]]:
    if len(keys) != len(values):
        raise ValueError("keys/values length mismatch")
    if not 0 <= query_index < len(keys):
        raise ValueError("query_index out of range")
    scores = [dot(query, key) / math.sqrt(len(query)) for key in keys]
    # 因果掩码：当前位置只能看见 0..query_index，未来位置分数设为 -inf。
    scores = [score if position <= query_index else -math.inf
              for position, score in enumerate(scores)]
    weights = softmax(scores)
    output = [
        sum(weight * value[dim] for weight, value in zip(weights, values))
        for dim in range(len(values[0]))
    ]
    return weights, output


def lora_parameters(d_out: int, d_in: int, rank: int) -> tuple[int, int]:
    if min(d_out, d_in, rank) <= 0 or rank > min(d_out, d_in):
        raise ValueError("invalid LoRA shape")
    full = d_out * d_in
    update = d_out * rank + rank * d_in
    return full, update


def recall_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    if not relevant:
        raise ValueError("relevant set must not be empty")
    return len(relevant.intersection(retrieved[:k])) / len(relevant)


def reciprocal_rank(relevant: set[str], retrieved: Sequence[str]) -> float:
    for index, item in enumerate(retrieved, 1):
        if item in relevant:
            return 1 / index
    return 0.0


def mrr(relevant_sets: Sequence[set[str]], retrieved_lists: Sequence[Sequence[str]]) -> float:
    if len(relevant_sets) != len(retrieved_lists) or not relevant_sets:
        raise ValueError("each query needs labels and results")
    return sum(
        reciprocal_rank(relevant, retrieved)
        for relevant, retrieved in zip(relevant_sets, retrieved_lists)
    ) / len(relevant_sets)