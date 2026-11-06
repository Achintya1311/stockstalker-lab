import pandas as pd

from strategies import e2a_a02_crowded, e2a_f11_fallback, f11_range_top_fade
from strategies.e2a_f11_fallback_audit import check_cross_symbol_causality

FLOOR = 25e7  # config/universe.yml: 25 crore


def _history(tradable: dict[str, bool], last_date="2016-02-01", n=20, turnover=30e7) -> pd.DataFrame:
    """n daily rows per symbol ending on `last_date`; has_future on the last row as given."""
    dates = pd.bdate_range(end=last_date, periods=n).strftime("%Y-%m-%d")
    rows = []
    for sym, fut in tradable.items():
        for i, d in enumerate(dates):
            rows.append({"date": d, "symbol": sym, "open": 100.0, "close": 100.0, "turnover": turnover,
                         "has_future": fut if i == n - 1 else True})
    return pd.DataFrame(rows)


def _stub(monkeypatch, e2a: dict, f11: dict):
    monkeypatch.setattr(e2a_a02_crowded, "score", lambda h: pd.Series(e2a, dtype=float))
    monkeypatch.setattr(f11_range_top_fade, "score", lambda h: pd.Series(f11, dtype=float))


def test_reads_e2a_when_it_has_a_tradable_bearish_pick(monkeypatch):
    _stub(monkeypatch, {"AAA": -0.04, "BBB": 0.02}, {"CCC": -0.3})
    out = e2a_f11_fallback.score(_history({"AAA": True, "BBB": True, "CCC": True}))
    pd.testing.assert_series_equal(out, pd.Series({"AAA": -0.04}, dtype=float))


def test_falls_back_to_f11_when_e2a_has_no_bearish_pick(monkeypatch):
    _stub(monkeypatch, {"BBB": 0.02}, {"CCC": -0.3, "DDD": 0.2, "EEE": -0.1})
    out = e2a_f11_fallback.score(_history({"BBB": True, "CCC": True, "DDD": True, "EEE": True}))
    pd.testing.assert_series_equal(out, pd.Series({"CCC": -0.3, "EEE": -0.1}, dtype=float))


def test_falls_back_when_e2a_pick_has_no_future_at_last_close(monkeypatch):
    _stub(monkeypatch, {"AAA": -0.04}, {"CCC": -0.3})
    out = e2a_f11_fallback.score(_history({"AAA": False, "CCC": True}))
    assert list(out.index) == ["CCC"]


def test_falls_back_when_e2a_pick_is_below_the_turnover_floor(monkeypatch):
    _stub(monkeypatch, {"AAA": -0.04}, {"CCC": -0.3})
    h = _history({"AAA": True, "CCC": True})
    h.loc[h["symbol"] == "AAA", "turnover"] = FLOOR * 0.5
    assert e2a_f11_fallback.chosen_member(h)[0] == "f11"


def test_falls_back_when_e2a_pick_is_a_stale_symbol(monkeypatch):
    """A symbol with no row on the slice's last date (delisted or merged) does not count."""
    _stub(monkeypatch, {"OLD": -0.04}, {"CCC": -0.3})
    h = pd.concat([_history({"OLD": True}, last_date="2016-01-15"), _history({"CCC": True})], ignore_index=True)
    assert e2a_f11_fallback.tradable_at_last_close(h) == {"CCC"}
    assert e2a_f11_fallback.chosen_member(h)[0] == "f11"


def test_short_turnover_window_is_not_tradable():
    h = _history({"AAA": True}, n=10)
    assert e2a_f11_fallback.tradable_at_last_close(h) == set()


def test_never_bullish(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": 1.0, "DDD": 0.5})
    assert e2a_f11_fallback.score(_history({"CCC": True, "DDD": True})).empty


def test_empty_history():
    assert e2a_f11_fallback.score(pd.DataFrame()).empty


def test_rules_fired_names_the_member_and_wording_is_safe(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": -0.3})
    h = _history({"CCC": True})
    picked = e2a_f11_fallback.rules_fired(h, "CCC")
    skipped = e2a_f11_fallback.rules_fired(h, "ZZZ")
    assert "F11" in picked and "-0.3000 (bearish)" in picked
    assert "abstain" in skipped
    for text in (picked, skipped):
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
