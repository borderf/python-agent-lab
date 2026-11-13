import math

import pytest

from practice.ai_foundations.checks import (
    cosine,
    dot,
    lora_parameters,
    masked_attention,
    mrr,
    recall_at_k,
    reciprocal_rank,
    softmax,
)


def test_softmax_and_temperature():
    assert math.isclose(sum(softmax([2.0, 1.0, 0.0])), 1.0)
    sharp = softmax([2.0, 1.0, 0.0], 0.5)
    flat = softmax([2.0, 1.0, 0.0], 2.0)
    assert sharp[0] > flat[0]
    with pytest.raises(ValueError):
        softmax([1.0], 0)


def test_cosine_and_dimension_boundary():
    assert math.isclose(cosine([1, 0], [1, 0]), 1.0)
    assert math.isclose(cosine([1, 0], [0, 1]), 0.0)
    with pytest.raises(ValueError):
        cosine([1, 0], [1, 0, 0])
    with pytest.raises(ValueError):
        cosine([0, 0], [1, 0])


def test_masked_attention_weights_and_output():
    weights, output = masked_attention(
        [1.0, 0.0],
        [[1.0, 0.0], [0.0, 1.0]],
        [[10.0, 0.0], [0.0, 10.0]],
        0,
    )
    assert math.isclose(sum(weights), 1.0)
    assert math.isclose(weights[0], 1.0, abs_tol=1e-12)
    assert math.isclose(weights[1], 0.0, abs_tol=1e-12)
    assert math.isclose(output[0], 10.0)
    assert math.isclose(output[1], 0.0)

    later, _ = masked_attention(
        [1.0, 0.0],
        [[1.0, 0.0], [0.0, 1.0]],
        [[10.0, 0.0], [0.0, 10.0]],
        1,
    )
    assert later[1] > 0
    with pytest.raises(ValueError):
        masked_attention([1.0], [[1.0]], [[1.0]], 1)


def test_lora_parameter_count():
    full, update = lora_parameters(4096, 4096, 8)
    assert full == 4096 * 4096
    assert update == 4096 * 8 + 8 * 4096
    assert update < full


def test_recall_rr_and_mrr():
    assert recall_at_k({"d1", "d3"}, ["d1", "d2", "d3"], 3) == 1.0
    assert reciprocal_rank({"d1", "d3"}, ["d2", "d1", "d3"]) == 0.5
    assert mrr(
        [{"d1", "d3"}, {"d2"}],
        [["d1", "d2", "d3"], ["d1", "d2"]],
    ) == 0.75
    with pytest.raises(ValueError):
        mrr([], [])


def test_dot_rejects_mismatch():
    with pytest.raises(ValueError):
        dot([1, 2], [1])