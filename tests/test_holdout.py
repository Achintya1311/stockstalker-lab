import random

import pytest

from engine.holdout import ThresholdoutAnswer, thresholdout_query


def test_close_values_release_train_value_for_free():
    # train and holdout agree well within threshold + any noise a fixed seed draws
    rng = random.Random(1)
    answer = thresholdout_query(0.05, 0.051, threshold=0.03, tolerance=0.001, rng=rng)
    assert answer.budget_spent is False
    assert answer.released_value == answer.train_value == 0.05


def test_far_apart_values_release_a_holdout_derived_answer():
    rng = random.Random(1)
    answer = thresholdout_query(0.05, 0.40, threshold=0.03, tolerance=0.001, rng=rng)
    assert answer.budget_spent is True
    # released value tracks holdout (plus small noise), not train
    assert abs(answer.released_value - 0.40) < 0.01
    assert answer.released_value != answer.train_value


def test_true_holdout_value_never_appears_unmodified_when_budget_is_spent():
    rng = random.Random(1)
    answer = thresholdout_query(0.0, 1.0, threshold=0.03, tolerance=0.001, rng=rng)
    assert answer.budget_spent is True
    assert answer.released_value != 1.0  # noise is always added, never a bare pass-through


def test_identical_values_rarely_spend_budget_when_tolerance_is_small_next_to_threshold():
    # With threshold=0.03 and tolerance=0.001 (2*tolerance=0.002 Laplace scale
    # on the comparison noise xi), P(xi < -0.03) = 0.5 * exp(-0.03/0.002) is
    # astronomically small - unlike a threshold only ~1.5x the noise scale
    # (where a double-digit false-positive rate is normal, not a bug: that
    # case is covered by test_far_apart_values_release_a_holdout_derived_answer's
    # sibling cases, not here).
    for seed in range(50):
        rng = random.Random(seed)
        answer = thresholdout_query(0.1, 0.1, threshold=0.03, tolerance=0.001, rng=rng)
        if answer.budget_spent:
            pytest.fail(f"seed {seed} spent budget on identical train/holdout values")


def test_default_rng_gives_a_valid_answer_without_a_seed():
    answer = thresholdout_query(0.05, 0.051, threshold=0.03, tolerance=0.001)
    assert isinstance(answer, ThresholdoutAnswer)
    assert isinstance(answer.released_value, float)


def test_answer_is_deterministic_given_the_same_seeded_rng_state():
    a = thresholdout_query(0.05, 0.4, threshold=0.03, tolerance=0.01, rng=random.Random(7))
    b = thresholdout_query(0.05, 0.4, threshold=0.03, tolerance=0.01, rng=random.Random(7))
    assert a == b
