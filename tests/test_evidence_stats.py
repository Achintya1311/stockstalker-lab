import numpy as np
import pandas as pd

from scripts.evidence_stats import block_size, boot_ci, multiple_testing


def _noise(n_dates=800, n_models=20, seed=0, sd=0.05):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n_dates)
    return pd.DataFrame(rng.normal(0, sd, (n_dates, n_models)), index=idx, columns=[f"s{i}" for i in range(n_models)])


def test_ci_covers_a_known_mean_and_excludes_zero_for_a_real_edge():
    rng = np.random.default_rng(1)
    x = rng.normal(0.02, 0.05, 1000)
    r = boot_ci(x, reps=800)
    assert r["lo"] < 0.02 < r["hi"] and r["lo"] > 0 and r["p_le0"] < 0.01


def test_autocorrelated_series_gets_a_wider_interval_than_iid_would():
    rng = np.random.default_rng(2)
    e = rng.normal(0, 1, 1500)
    x = np.zeros(1500)
    for i in range(1, 1500):
        x[i] = 0.7 * x[i - 1] + e[i]
    assert block_size(x) > 1
    r = boot_ci(x, reps=600)
    assert (r["hi"] - r["lo"]) > 2 * 1.96 * x.std() / np.sqrt(len(x))


def test_planted_edge_is_found_among_noise_and_pure_noise_is_not():
    noise = _noise()
    planted = noise.copy()
    planted["real"] = np.random.default_rng(9).normal(0.012, 0.05, len(planted))  # t about 6
    out = multiple_testing(planted, reps=600)
    assert "real" in out["stepm"] and out["spa"]["consistent"] < 0.05
    quiet = multiple_testing(noise, reps=600)
    assert quiet["stepm"] == [] and quiet["spa"]["consistent"] > 0.05
