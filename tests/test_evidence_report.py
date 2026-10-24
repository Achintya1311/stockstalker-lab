import numpy as np
import pandas as pd

from scripts.evidence_report import render


def test_render_names_the_groups_and_does_not_crash_on_a_minimal_result():
    res = {"day/bearish": {"experiments": {"a02": {"mean": 0.04, "lo": 0.02, "hi": 0.06, "p_le0": 0.0, "block": 3, "n": 1000, "coverage": 0.9}},
                           "joint": {"n_models": 1, "block": 3, "spa": {"consistent": 0.01, "lower": 0.01, "upper": 0.01}, "stepm": ["a02"], "mcs": ["a02"]}}}
    md = render(res)
    assert "day/bearish" in md and "a02" in md and "+4.00" in md
