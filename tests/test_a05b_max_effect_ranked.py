import numpy as np
import pandas as pd
import pytest

from strategies import a05_max_effect, a05b_max_effect_ranked as a05b
from strategies.a05b_max_effect_ranked_audit import check_cross_symbol_causality


def _realistic_series(symbol: str, best_day: float, seed: int, n_rows: int | None = None) -> pd.DataFrame:
    """A mixed up-and-down series whose MAX window's best day is `best_day`.

    Unlike v1's bullish fixture (every month day falling), every window here
    has both up and down days, so `z` is positive like it is on real data.
    The baseline alternates +-1%, so sigma is exactly 0.01; the MAX window
    alternates +-0.5% with one day of `best_day`, so MAX is `best_day` and
    `z = best_day / 0.01` whenever `best_day >= 0.005`.
    """
    rng = np.random.default_rng(seed)
    n_rows = n_rows or a05_max_effect.MIN_ROWS + 10
    lead = n_rows - a05_max_effect.MIN_ROWS
    steps = list(rng.choice([0.004, -0.004], size=lead))
    steps += [0.01 if i % 2 == 0 else -0.01 for i in range(a05_max_effect.SIGMA_WINDOW)]
    month = [0.005 if i % 2 == 0 else -0.005 for i in range(a05_max_effect.MAX_WINDOW)]
    month[10] = best_day
    steps += month

    closes = [100.0]
    for s in steps:
        closes.append(closes[-1] * (1 + s))
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows, prev = [], closes[0]
    for date, close in zip(dates, closes):
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev,
                "high": max(prev, close),
                "low": min(prev, close),
                "close": close,
                "prevclose": prev,
                "volume": 1_000_000.0,
            }
        )
        prev = close
    return pd.DataFrame(rows)


def _universe(best_days: dict[str, float]) -> pd.DataFrame:
    return pd.concat(
        [_realistic_series(sym, bd, seed=i) for i, (sym, bd) in enumerate(best_days.items())],
        ignore_index=True,
    )


def test_realistic_month_is_bearish_in_v1_but_ranked_can_be_bullish():
    # The defect A05B exists to fix: on a realistic month v1 can only say bearish.
    history = _universe({"LOW": 0.01, "MID": 0.02, "HIGH": 0.05})
    v1 = a05_max_effect.score(history)
    assert (v1 < 0).all()
    ranked = a05b.score(history)
    assert ranked["LOW"] > 0
    assert ranked["HIGH"] < 0


def test_known_ranks_give_known_scores():
    # z = 1, 2, 3 -> mid-rank pct = 1/6, 1/2, 5/6 -> score = +2/3, 0 (abstain), -2/3.
    history = _universe({"A": 0.01, "B": 0.02, "C": 0.03})
    z = a05b._z_by_symbol(history)
    assert z["A"] == pytest.approx(1.0, rel=1e-6)
    assert z["C"] == pytest.approx(3.0, rel=1e-6)
    scores = a05b.score(history)
    assert scores["A"] == pytest.approx(2 / 3)
    assert scores["C"] == pytest.approx(-2 / 3)
    assert "B" not in scores.index  # exactly the median: abstain


def test_even_field_has_no_median_and_is_symmetric():
    # z = 1..4 -> pct = 1/8, 3/8, 5/8, 7/8 -> score = 0.75, 0.25, -0.25, -0.75.
    scores = a05b.score(_universe({"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04}))
    assert list(scores.sort_index().round(6)) == [0.75, 0.25, -0.25, -0.75]
    assert scores.sum() == pytest.approx(0.0)


def test_scores_are_balanced_across_sides():
    history = _universe({f"S{i}": 0.006 + 0.004 * i for i in range(9)})
    scores = a05b.score(history)
    assert (scores > 0).sum() == (scores < 0).sum() == 4


def test_single_symbol_abstains():
    # A lone stock is its own median (pct = 0.5): no peers, no direction.
    assert a05b.score(_universe({"ONLY": 0.02})).empty


def test_ties_share_a_rank():
    scores = a05b.score(_universe({"A": 0.01, "B": 0.03, "C": 0.03}))
    assert scores["B"] == pytest.approx(scores["C"])
    assert scores["A"] > 0 > scores["B"]


def test_insufficient_history_abstains_and_is_not_a_peer():
    short = _realistic_series("SHORT", 0.05, seed=9).iloc[-(a05_max_effect.MIN_ROWS - 1) :]
    history = pd.concat([_universe({"A": 0.01, "B": 0.03}), short], ignore_index=True)
    scores = a05b.score(history)
    assert "SHORT" not in scores.index
    # Ranked against B only (pct 1/4): if SHORT counted as a peer A would be 1/6.
    assert scores["A"] == pytest.approx(0.5)


def test_has_future_prefilter():
    history = _universe({"A": 0.01, "B": 0.02, "C": 0.03})
    history["has_future"] = history["symbol"] != "C"
    scores = a05b.score(history)
    assert "C" not in scores.index
    assert scores["A"] > 0 and scores["B"] < 0


def test_empty_history():
    assert a05b.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    history = _universe({"A": 0.01, "B": 0.02, "C": 0.03})
    text = a05b.rules_fired(history, "A")
    assert "bullish" in text and "A05B" in text
    assert "abstain" in a05b.rules_fired(history, "B")
    assert "abstain" in a05b.rules_fired(history, "MISSING")
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()


def test_cross_symbol_causality_audit():
    result = check_cross_symbol_causality()
    assert result["passed"], result
