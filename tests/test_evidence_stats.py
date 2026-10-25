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


def test_identical_trials_do_not_break_the_joint_tests_and_share_membership():
    # Two trials with the same picks on every date give identical edge series; arch's MCS used to
    # fail on the zero-variance difference (evidence run 40214739477, A05 vs A05B bearish).
    planted = _noise(n_models=6)
    planted["real"] = np.random.default_rng(9).normal(0.012, 0.05, len(planted))
    planted["real_twin"] = planted["real"]
    planted["s0_twin"] = planted["s0"]
    out = multiple_testing(planted, reps=400)
    assert out["n_models"] == 9
    assert out["twins"] == {"real_twin": "real", "s0_twin": "s0"}
    assert "real" in out["stepm"] and "real_twin" in out["stepm"]
    assert ("s0" in out["mcs"]) == ("s0_twin" in out["mcs"])
