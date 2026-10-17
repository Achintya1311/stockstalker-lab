import pandas as pd
import pytest

from engine.replay import SplitViolation, authorize, hash_picks, load_pick_log, pick_date, run_dates, truncate

SPLITS = {
    "train": {"start": "2015-01-01", "end": "2020-12-31"},
    "validation": {"start": "2021-01-01", "end": "2023-12-31"},
    "test": {"start": "2024-01-01", "end": "2026-07-31"},
    "exam": {"start": "2026-08-01", "end": "go-live"},
}


def _history(dates, symbol="ABC"):
    return pd.DataFrame({"date": dates, "symbol": [symbol] * len(dates), "close": range(len(dates))})


class _SeenDatesStrategy:
    """Records every date it was ever shown, so a test can assert what leaked in."""

    def __init__(self):
        self.seen_dates = []

    def score(self, history: pd.DataFrame) -> pd.Series:
        self.seen_dates.extend(history["date"].tolist())
        return pd.Series(1.0, index=history["symbol"].unique())


class _AbstainingStrategy:
    def score(self, history: pd.DataFrame) -> pd.Series:
        symbols = history["symbol"].unique()
        # abstain on everything but the first symbol
        values = [1.0 if i == 0 else float("nan") for i in range(len(symbols))]
        return pd.Series(values, index=symbols)


def test_truncate_excludes_the_pick_date_and_everything_after():
    hist = _history(["2015-01-01", "2015-01-02", "2015-01-03"])
    out = truncate(hist, "2015-01-02")
    assert out["date"].tolist() == ["2015-01-01"]


def test_truncate_before_any_data_is_empty():
    hist = _history(["2015-01-01", "2015-01-02"])
    out = truncate(hist, "2015-01-01")
    assert out.empty


def test_authorize_accepts_date_inside_split():
    authorize("2015-06-01", "train", SPLITS)  # must not raise


def test_authorize_rejects_date_outside_split_start():
    with pytest.raises(SplitViolation):
        authorize("2014-12-31", "train", SPLITS)


def test_authorize_rejects_validation_date_for_a_train_job():
    with pytest.raises(SplitViolation):
        authorize("2021-06-01", "train", SPLITS)


def test_authorize_rejects_test_date_for_a_train_job():
    with pytest.raises(SplitViolation):
        authorize("2024-06-01", "train", SPLITS)


def test_authorize_rejects_unknown_split():
    with pytest.raises(SplitViolation):
        authorize("2015-06-01", "nope", SPLITS)


def test_authorize_accepts_open_ended_exam_split_on_or_after_start():
    authorize("2026-08-01", "exam", SPLITS)
    authorize("2027-01-01", "exam", SPLITS)  # far beyond any fixed end, still fine


def test_pick_date_never_shows_the_strategy_the_pick_dates_own_row_or_later():
    hist = _history(["2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04"])
    strategy = _SeenDatesStrategy()
    pick_date(hist, strategy, "2015-01-03", "train", SPLITS)
    assert strategy.seen_dates == ["2015-01-01", "2015-01-02"]
    assert max(strategy.seen_dates) < "2015-01-03"


def test_pick_date_refuses_a_date_outside_the_authorised_split():
    hist = _history(["2021-01-01", "2021-01-02"])
    strategy = _SeenDatesStrategy()
    with pytest.raises(SplitViolation):
        pick_date(hist, strategy, "2021-01-02", "train", SPLITS)
    # refused before the strategy ever ran
    assert strategy.seen_dates == []


def test_pick_date_drops_abstaining_symbols():
    hist = pd.DataFrame({
        "date": ["2015-01-01"] * 3,
        "symbol": ["AAA", "BBB", "CCC"],
        "close": [1, 2, 3],
    })
    strategy = _AbstainingStrategy()
    out = pick_date(hist, strategy, "2015-01-02", "train", SPLITS)
    assert list(out["symbol"]) == ["AAA"]


def test_run_dates_sees_only_dates_before_each_respective_pick_date():
    hist = _history(["2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04", "2015-01-05"])
    strategy = _SeenDatesStrategy()
    run_dates(hist, strategy, ["2015-01-03", "2015-01-05"], "train", SPLITS)
    # second call (picking 2015-01-05) must never have seen 2015-01-05 itself,
    # and the walk is strictly date-by-date: nothing from a later pick leaks
    # into an earlier one's view either.
    assert "2015-01-05" not in strategy.seen_dates
    assert strategy.seen_dates == ["2015-01-01", "2015-01-02", "2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04"]


def test_run_dates_raises_on_a_single_bad_date_and_returns_no_picks_at_all():
    hist = _history(["2015-01-01", "2015-01-02", "2021-01-02"])
    strategy = _SeenDatesStrategy()
    with pytest.raises(SplitViolation):
        run_dates(hist, strategy, ["2015-01-02", "2021-01-02"], "train", SPLITS)


def test_hash_picks_is_independent_of_row_and_column_order():
    a = pd.DataFrame({"date": ["2015-01-02", "2015-01-01"], "symbol": ["BBB", "AAA"], "score": [2.0, 1.0]})
    b = pd.DataFrame({"symbol": ["AAA", "BBB"], "score": [1.0, 2.0], "date": ["2015-01-01", "2015-01-02"]})
    assert hash_picks(a) == hash_picks(b)


def test_hash_picks_changes_if_a_pick_changes():
    a = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["AAA"], "score": [1.0]})
    b = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["AAA"], "score": [2.0]})
    assert hash_picks(a) != hash_picks(b)


def test_hash_picks_is_computed_before_any_outcome_column_exists():
    # The pick log at hash time carries no close/hit/outcome column at all -
    # hashing never has the chance to depend on one.
    picks = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["AAA"], "score": [1.0]})
    assert "outcome" not in picks.columns and "hit" not in picks.columns
    h = hash_picks(picks)
    assert len(h) == 64  # sha256 hex digest


def test_hash_picks_is_unchanged_by_a_whole_number_score_becoming_int64():
    # A score column that is every value 1.0 round-trips through JSON (the
    # committed pick-log format) as int64, not float64 - the hash must not
    # care, or a verifier re-hashing the committed file gets a false mismatch.
    as_float = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["AAA"], "score": pd.array([1.0], dtype="float64")})
    as_int = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["AAA"], "score": pd.array([1], dtype="int64")})
    assert hash_picks(as_float) == hash_picks(as_int)


def test_load_pick_log_round_trips_through_json_with_a_matching_hash(tmp_path):
    picks = pd.DataFrame({
        "date": ["2015-01-02", "2015-01-02", "2015-01-05"],
        "symbol": ["AAA", "BBB", "AAA"],
        "score": [1.0, 1.0, 1.0],
    })
    original_hash = hash_picks(picks)

    path = tmp_path / "picks.json"
    path.write_text(picks.to_json(orient="records", indent=2) + "\n")

    reloaded = load_pick_log(path)
    assert hash_picks(reloaded) == original_hash
