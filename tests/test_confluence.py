"""Synthetic tests for CONFLUENCE_V1 (`strategies/confluence_core.py`), its audit, held replays, card and report.

Each component's True / False / None cases on hand-built bars, bullish / bearish mirror symmetry (prices flipped
about a level flip the side), the setup requirement (a location AND an event), nested minimum counts, the
both-sides abstention, ablation semantics, the tie-break range, no look-ahead, and the pre-declared rule and
selection in the report.
"""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from engine.replay import truncate
from scripts import confluence_report as rep
from strategies import confluence_core as C
from strategies import g_gates as G
from strategies.confluence_audit import run_all
from strategies.g_gates_audit import synthetic_panel
from tests.test_reasoning_no_price_levels import LEVEL

ROOT = Path(__file__).resolve().parent.parent
HELD = ROOT / "experiments" / "held" / "conf"
PENDING = ROOT / "experiments" / "pending"
CARD = ROOT / "cards" / "CONFLUENCE_V1.yml"
CATALOG = ROOT / "cards" / "catalog.csv"


# ---------------------------------------------------------------- hand-built bars


def flip_arrays(o, h, l, c, level: float = 200.0):
    return 2 * level - o, 2 * level - l, 2 * level - h, 2 * level - c


def flip_panel(df: pd.DataFrame, level: float = 500.0) -> pd.DataFrame:
    out = df.copy()
    for col in ("open", "close", "prevclose"):
        out[col] = 2 * level - df[col]
    out["high"], out["low"] = 2 * level - df["low"], 2 * level - df["high"]
    return out


def ob_bars(last_close: float = 101.5):
    """60 quiet bars (range 2), a down candle (the zone, 99-101), an up impulse closing above the 10-bar high,
    then a drift back toward the zone ending at `last_close`. range20 = 7.5, so 'near' is 0.75."""
    o, h, l, c = [], [], [], []
    for i in range(60):
        o.append(100.0); c.append(100.5 if i % 2 == 0 else 99.5); h.append(101.0); l.append(99.0)
    o.append(100.5); c.append(99.5); h.append(101.0); l.append(99.0)
    o.append(99.5); c.append(106.0); h.append(106.5); l.append(99.4)
    prev = 106.0
    for x in np.linspace(105.5, last_close, 8):
        o.append(prev); c.append(x); h.append(max(prev, x) + 0.1); l.append(min(prev, x) - 0.1); prev = x
    return tuple(np.array(v, dtype=float) for v in (o, h, l, c))


def sr_bars(end: float = 100.6):
    """A fall to a unique swing low (99.5), a rise to a swing high, a fall back to `end` (46 bars)."""
    c = np.array(list(np.linspace(110, 100, 11)) + list(np.linspace(101.7, 115, 15)) + list(np.linspace(114, end, 20)))
    o = (np.r_[c[0], c[:-1]] + c) / 2
    return o, np.maximum(o, c) + 0.5, np.minimum(o, c) - 0.5, c


def flat_bars(n: int, low: float = 99.0, high: float = 101.0):
    o = np.full(n, 100.0); c = np.full(n, 100.2)
    return o, np.full(n, high), np.full(n, low), c


def with_last(bars, o1, h1, l1, c1):
    o, h, l, c = bars
    return np.r_[o, o1], np.r_[h, h1], np.r_[l, l1], np.r_[c, c1]


def history_from(bars, symbol: str = "AAA", oi: tuple[float, float] | None = None) -> pd.DataFrame:
    o, h, l, c = bars
    n = len(c)
    df = pd.DataFrame({
        "date": pd.bdate_range("2016-01-01", periods=n).strftime("%Y-%m-%d"),
        "symbol": symbol, "open": o, "high": h, "low": l, "close": c,
        "prevclose": np.r_[c[0], c[:-1]], "volume": 1e6, "has_future": True,
    })
    if oi is not None:
        df["oi_futstk"], df["oi_chg_futstk"] = oi
    return df


# ---------------------------------------------------------------- components


def test_order_block_true_false_none_and_mirror():
    bars = ob_bars()
    assert C.order_block(*bars, 1) is True
    assert C.order_block(*bars, -1) is False          # the zone is a demand zone
    assert C.order_block(*ob_bars(104.0), 1) is False  # 3 above the zone > 0.10 x range20
    assert C.order_block(*(b[-59:] for b in bars), 1) is None
    flipped = flip_arrays(*bars)
    assert C.order_block(*flipped, -1) is True and C.order_block(*flipped, 1) is False


def test_support_resistance_true_false_none_and_mirror():
    bars = sr_bars()
    assert C.support_resistance(*bars, 1) is True
    assert C.support_resistance(*bars, -1) is False    # nearest swing high is far above
    assert C.support_resistance(*sr_bars(106.0), 1) is False
    assert C.support_resistance(*(b[-44:] for b in bars), 1) is None
    flipped = flip_arrays(*bars)
    assert C.support_resistance(*flipped, -1) is True and C.support_resistance(*flipped, 1) is False


def test_support_resistance_uses_the_chart_swing_function(monkeypatch):
    calls = []
    real = C.chart.swing_levels
    monkeypatch.setattr(C.chart, "swing_levels", lambda bars: calls.append(len(bars)) or real(bars))
    C.support_resistance(*sr_bars(), 1)
    assert calls == [C.SR_BARS]


def test_liquidity_sweep_cases_and_mirror():
    base = flat_bars(10)
    ok = with_last(base, 99.5, 100.0, 98.0, 99.6)        # took the 10-session low (99), closed back above
    held, strength = C.liquidity_sweep(ok[1], ok[2], ok[3], 1)
    assert held is True and strength == pytest.approx(1.0 / 3.0)   # depth 1 / range20 3
    assert C.liquidity_sweep(ok[1], ok[2], ok[3], -1) == (False, 0.0)
    below = with_last(base, 99.5, 100.0, 98.0, 98.8)     # closed below the old low
    assert C.liquidity_sweep(below[1], below[2], below[3], 1)[0] is False
    shallow = with_last(base, 99.5, 100.0, 99.2, 99.6)   # never took the low
    assert C.liquidity_sweep(shallow[1], shallow[2], shallow[3], 1)[0] is False
    short = tuple(b[-10:] for b in ok)
    assert C.liquidity_sweep(short[1], short[2], short[3], 1)[0] is None
    f = flip_arrays(*ok)
    assert C.liquidity_sweep(f[1], f[2], f[3], -1) == pytest.approx((True, 1.0 / 3.0))
    assert C.liquidity_sweep(f[1], f[2], f[3], 1)[0] is False


def test_candle_engulfing_hammer_and_mirror():
    prev = (np.array([101.0]), np.array([101.2]), np.array([99.8]), np.array([100.0]))   # down bar
    engulf = with_last(prev, 99.9, 101.4, 99.8, 101.2)
    held, s = C.candle(*engulf, 1)
    assert held is True and s == pytest.approx(1.3 / 1.6)
    assert C.candle(*engulf, -1)[0] is False
    small = with_last(prev, 100.2, 100.9, 100.1, 100.8)   # up bar inside the prior body
    assert C.candle(*small, 1)[0] is False
    hammer = with_last(flat_bars(1), 100.0, 100.4, 99.0, 100.3)  # body 0.3, lower wick 1.0, close in top third
    held, s = C.candle(*hammer, 1)
    assert held is True and s == pytest.approx(1.0 / 1.4)
    no_top_third = with_last(flat_bars(1), 100.0, 101.5, 99.0, 99.9)
    assert C.candle(*no_top_third, 1)[0] is False
    assert C.candle(*(b[-1:] for b in hammer), 1)[0] is None
    for bars in (engulf, hammer):
        f = flip_arrays(*bars)
        assert C.candle(*f, -1) == pytest.approx(C.candle(*bars, 1))
        assert C.candle(*f, 1)[0] is False


def test_ema_trend_cases_and_mirror():
    up = 100.0 * 1.003 ** np.arange(120)
    assert C.ema_trend(up, 1) is True and C.ema_trend(up, -1) is False
    assert C.ema_trend(up[::-1], -1) is True and C.ema_trend(up[::-1], 1) is False
    assert C.ema_trend(up[:99], 1) is None
    assert C.ema_trend(400.0 - up, -1) is True


def test_open_interest_component_is_g7():
    bars = with_last(flat_bars(30), 100.0, 101.5, 99.9, 101.0)      # last session up
    built = C.components(history_from(bars, oi=(110_000.0, 10_000.0)))    # OI up: long build-up, D01C bearish
    assert built.at["AAA", "oi_bear"] is not None and bool(built.at["AAA", "oi_bear"]) is True
    assert built.at["AAA", "oi_bull"] is not None and bool(built.at["AAA", "oi_bull"]) is False
    none = C.components(history_from(bars))                           # no futures OI columns
    assert none.at["AAA", "oi_bull"] is None and none.at["AAA", "oi_bear"] is None


@pytest.mark.parametrize("trend,stress,bull,bear", [
    ((2.0, 1.0), (0.01, 0.02), True, False),    # uptrend, calm
    ((2.0, 1.0), (0.03, 0.02), False, False),   # uptrend, stressed
    ((1.0, 2.0), (0.03, 0.02), False, True),    # downtrend, stressed
    ((1.0, 2.0), (0.01, 0.02), False, False),   # downtrend, calm
    (None, (0.01, 0.02), None, None),
    ((2.0, 1.0), None, None, None),
])
def test_market_backdrop(monkeypatch, trend, stress, bull, bear):
    monkeypatch.setattr(G, "market_trend_reading", lambda adj: trend)
    monkeypatch.setattr(G, "stress_reading", lambda adj, quantile=None: stress)
    assert C.market_backdrop(pd.DataFrame()) == {1: bull, -1: bear}


def test_components_table_marks_short_history_none():
    built = C.components(history_from(flat_bars(15)))
    for comp in ("ob", "sr", "ema", "market"):
        assert built.at["AAA", f"{comp}_bull"] is None and built.at["AAA", f"{comp}_bear"] is None


# ---------------------------------------------------------------- mirror symmetry on a panel


def test_flipping_prices_flips_every_per_symbol_component():
    panel = synthetic_panel(n_rows=200)
    d = sorted(panel["date"].unique())[-1]
    a = C.components(truncate(panel, d)).copy()
    b = C.components(truncate(flip_panel(panel), d)).copy()
    assert list(a.index) == list(b.index) and len(a) == 10
    for comp in ("ob", "sr", "sweep", "candle", "ema", "oi"):
        for s in a.index:
            assert a.at[s, f"{comp}_bull"] == b.at[s, f"{comp}_bear"], (comp, s)
            assert a.at[s, f"{comp}_bear"] == b.at[s, f"{comp}_bull"], (comp, s)
    for e in C.EVENTS:
        assert np.allclose(a[f"{e}_bull_strength"].astype(float), b[f"{e}_bear_strength"].astype(float))


def test_flipping_prices_flips_the_side_of_every_score():
    panel = synthetic_panel(n_rows=200)   # under 270 universe returns: market component None both ways
    flipped = flip_panel(panel)
    seen = 0
    for d in sorted(panel["date"].unique())[-30:]:
        a = C.config_score("confluence_min3", truncate(panel, d))
        b = C.config_score("confluence_min3", truncate(flipped, d))
        assert set(a.index) == set(b.index)
        assert np.allclose(a.sort_index().to_numpy(), -b.sort_index().to_numpy())
        seen += len(a)
    assert seen > 0


# ---------------------------------------------------------------- setups, counts, abstention, ablations


def table(rows: dict[str, dict]) -> pd.DataFrame:
    cols = {f"{c}_{s}": False for c in C.COMPONENTS for s in ("bull", "bear")}
    cols.update({f"{e}_{s}_strength": 0.0 for e in C.EVENTS for s in ("bull", "bear")})
    return pd.DataFrame.from_dict({k: {**cols, **v} for k, v in rows.items()}, orient="index")


def test_setup_needs_a_location_and_an_event():
    t = table({
        "LOC": {"ob_bull": True, "ema_bull": True, "oi_bull": True, "market_bull": True},
        "EVT": {"sweep_bull": True, "ema_bull": True, "oi_bull": True, "market_bull": True},
        "BOTH": {"sr_bull": True, "candle_bull": True, "candle_bull_strength": 0.5},
        "BEAR": {"ob_bear": True, "sweep_bear": True, "sweep_bear_strength": 0.1, "ema_bear": True},
    })
    st = C.setups(t)
    assert set(st.index) == {"BOTH", "BEAR"}
    assert st.loc["BOTH", "side"] == 1 and st.loc["BOTH", "count"] == 2
    assert st.loc["BEAR", "side"] == -1 and st.loc["BEAR", "count"] == 3


def test_none_counts_as_not_true():
    t = table({"X": {"ob_bull": True, "sweep_bull": True, "ema_bull": None, "oi_bull": None, "market_bull": None}})
    assert C.setups(t).loc["X", "count"] == 2


def test_both_sides_abstain():
    t = table({"X": {"ob_bull": True, "sweep_bull": True, "sr_bear": True, "candle_bear": True},
               "Y": {"ob_bull": True, "sweep_bull": True, "sr_bear": True}})       # bearish has no event
    st = C.setups(t)
    assert "X" not in st.index and st.loc["Y", "side"] == 1


def test_counts_are_nested_and_scores_equal(monkeypatch):
    t = table({
        "C2": {"ob_bull": True, "sweep_bull": True},
        "C3": {"ob_bull": True, "sweep_bull": True, "ema_bull": True},
        "C4": {"sr_bear": True, "candle_bear": True, "ema_bear": True, "oi_bear": True},
        "C5": {"ob_bull": True, "sr_bull": True, "sweep_bull": True, "candle_bull": True, "oi_bull": True},
        "C7": {f"{c}_bear": True for c in C.COMPONENTS},
    })
    monkeypatch.setattr(C, "components", lambda history: t)
    sc = {k: C.config_score(f"confluence_min{k}", pd.DataFrame()) for k in C.MIN_COUNTS}
    assert set(sc[3].index) == {"C3", "C4", "C5", "C7"}
    assert set(sc[4].index) == {"C4", "C5", "C7"}
    assert set(sc[5].index) == {"C5", "C7"}
    for k in (4, 5):
        assert all(sc[k][s] == sc[3][s] for s in sc[k].index)
    assert sc[5]["C7"] < -7 and -8 < sc[5]["C7"]
    assert 5 < sc[5]["C5"] < 6


def test_nested_on_a_random_panel():
    panel = synthetic_panel()
    total = 0
    for d in sorted(panel["date"].unique())[-25:]:
        h = truncate(panel, d)
        s3, s4, s5 = (C.config_score(f"confluence_min{k}", h) for k in (3, 4, 5))
        assert set(s5.index) <= set(s4.index) <= set(s3.index)
        total += len(s3)
    assert total > 0


def test_ablation_ignores_the_component_completely(monkeypatch):
    t = table({
        "ONLY_OB": {"ob_bull": True, "sweep_bull": True, "ema_bull": True, "oi_bull": True},
        "OI4": {"sr_bull": True, "candle_bull": True, "ema_bull": True, "oi_bull": True},
        "ONLY_SWEEP": {"sr_bear": True, "sweep_bear": True, "ema_bear": True, "market_bear": True},
        "BOTH_UNLESS_OB": {"ob_bull": True, "sweep_bull": True, "sr_bear": True, "candle_bear": True,
                           "ema_bear": True, "oi_bear": True},
    })
    monkeypatch.setattr(C, "components", lambda history: t)
    sc = lambda name: C.config_score(name, pd.DataFrame())   # noqa: E731
    assert {"ONLY_OB", "OI4", "ONLY_SWEEP"} <= set(sc("confluence_min4").index)
    assert "BOTH_UNLESS_OB" not in sc("confluence_min4").index           # both sides: abstain
    assert "ONLY_OB" not in sc("confluence_min4_no_ob").index             # ob cannot be the location
    assert sc("confluence_min4_no_ob")["BOTH_UNLESS_OB"] < 0              # without ob only the bearish setup is left
    assert "OI4" not in sc("confluence_min4_no_oi").index                 # oi not counted: 3 of 6
    assert "ONLY_SWEEP" not in sc("confluence_min4_no_sweep").index       # sweep cannot be the event
    assert "ONLY_SWEEP" not in sc("confluence_min4_no_market").index      # market not counted: 3 of 6
    st = C.config_setups("confluence_min4_no_ema", pd.DataFrame())
    assert all("ema" not in comps for comps in st["components"])


def test_tiebreak_ranks_event_strength_within_the_day():
    t = table({
        "A": {"ob_bull": True, "sweep_bull": True, "sweep_bull_strength": 0.1},
        "B": {"ob_bull": True, "sweep_bull": True, "sweep_bull_strength": 0.3},
        "Cc": {"ob_bear": True, "sweep_bear": True, "sweep_bear_strength": 0.2,
               "candle_bear": True, "candle_bear_strength": 0.9},
    })
    st = C.setups(t)
    assert st["tiebreak"].between(0, 1, inclusive="left").all()
    assert st.loc["A", "tiebreak"] < st.loc["Cc", "tiebreak"] < st.loc["B", "tiebreak"]
    assert st.loc["A", "tiebreak"] == pytest.approx(0.5 / 3)
    assert st.loc["Cc", "tiebreak"] == pytest.approx(0.5)   # sweep 1.5 / 3, candle (only one) 0.5 / 1: the larger
    assert st.loc["B", "tiebreak"] == pytest.approx(2.5 / 3)


def test_no_look_ahead_and_audit_passes():
    result = run_all()
    assert result["passed"], result


def test_memo_does_not_leak_between_histories():
    panel = synthetic_panel()
    ds = sorted(panel["date"].unique())
    a1 = C.config_score("confluence_min3", truncate(panel, ds[-1]))
    C.config_score("confluence_min3", truncate(panel, ds[-5]))
    a2 = C.config_score("confluence_min3", truncate(panel, ds[-1]))
    assert a1.sort_index().equals(a2.sort_index())


def test_empty_history():
    assert C.config_score("confluence_min3", synthetic_panel().iloc[0:0]).empty


# ---------------------------------------------------------------- modules, held replays, card, catalog


def test_thin_modules_match_configs_and_reasoning_names_no_level():
    panel = synthetic_panel()
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    assert len(C.CONFIGS) == 10
    for name in C.CONFIGS:
        mod = importlib.import_module(f"strategies.{name}")
        assert mod.score(h).sort_index().equals(C.config_score(name, h).sort_index())
        for s in h["symbol"].unique():
            text = mod.rules_fired(h, s)
            assert text.startswith(name.upper())
            assert not any(w in text.lower() for w in ("buy", "sell", "target", "stop"))
            assert not LEVEL.search(text)


def test_held_replays_in_the_declared_folders_and_none_pending():
    # A replay yml sits in held/conf/<folder>/, then pending/ once queued, and is removed when its result is in done/.
    expected = {}
    for folder, (names, horizon) in rep.FOLDERS.items():
        for n in names:
            expected[rep.experiment_id(n, horizon)] = (folder, n, horizon)
    assert len(expected) == 20
    for eid, (folder, n, horizon) in expected.items():
        paths = [q for q in (HELD / folder / f"{eid}.yml", PENDING / f"{eid}.yml") if q.exists()]
        if not paths:
            assert (ROOT / "experiments" / "done" / eid).exists()
            continue
        assert yaml.safe_load(paths[0].read_text()) == {
            "id": eid, "strategy": f"strategies.{n}", "split": "train", "horizon": horizon,
            "dates": {"start": "2015-01-01", "end": "2020-12-31"}}


def test_card_and_catalog_rows():
    card = yaml.safe_load(CARD.read_text())
    for field in ("source_url", "author", "license", "published_on", "claim_as_stated", "horizon", "rules_plain",
                  "params", "red_flags", "status"):
        assert field in card
    assert card["claim_as_stated"].startswith("none verified")
    flags = " ".join(card["red_flags"]).lower()
    assert "no volatility index" in flags and "overseas index" in flags and "20 train replays" in flags
    rule = card["default_params"]["success_rule_per_table"]
    assert rule["live_rule_train_edge_pts"] == {t: v for t, (_, v) in rep.LIVE.items()}
    assert rule["min_train_picks"] == rep.MIN_PICKS
    rows = {r[0]: r for r in csv.reader(CATALOG.open())}
    for name, cfg in C.CONFIGS.items():
        assert cfg.config_id in rows and rows[cfg.config_id][-1] == "held" and len(rows[cfg.config_id]) == 12


# ---------------------------------------------------------------- report


def test_report_runs_with_everything_pending(tmp_path):
    t = rep.build(tmp_path)
    assert t["configs"] == [] and t["ablations"] == [] and len(t["pending"]) == 20
    assert all(not s["final"] for s in t["selections"])
    assert all(d["selected"] is None for s in t["selections"] for d in s["tables"].values())
    md = rep.render_md(t)
    assert "none yet" in md and "no volatility index" in md
    assert rep.main(["--done", str(tmp_path), "--md", str(tmp_path / "a.md"), "--json", str(tmp_path / "a.json")]) == 0
    json.loads((tmp_path / "a.json").read_text())


def _block(edge: float, years: list[float], n: int = 900) -> dict:
    return {"n_picks": n, "n_dates": 400, "edge": edge, "edge_t": 3.0, "directional_move": 0.001,
            "by_year": [{"year": 2015 + i, "edge": e} for i, e in enumerate(years)]}


def _write(done: Path, eid: str, bull: dict, bear: dict) -> None:
    (done / eid).mkdir(parents=True)
    (done / eid / "results.json").write_text(json.dumps(
        {"id": eid, "split": "train", "selections": {"top": {"bullish": bull, "bearish": bear}}}))


def test_report_rule_selection_and_ablations(tmp_path):
    done = tmp_path
    live_years = {"t04": [0.03] * 6, "e2a": [0.07] * 6, "a05b": [0.02] * 6, "a01": [0.02] * 6}
    for table, (trig, _) in rep.LIVE.items():
        side = rep.TABLES[table][1]
        blk = _block(0.03, live_years[trig])
        _write(done, rep.TRIGGER_RUNS[trig], blk if side > 0 else {"n_picks": 0}, blk if side < 0 else {"n_picks": 0})
    good_day_bull = [0.06, 0.05, 0.05, 0.05, 0.05, 0.05]
    good_day_bear = [0.09, 0.09, 0.09, 0.09, 0.09, 0.09]
    # day: min3 qualifies on both, min4 better fit on bullish only, min5 too few picks
    _write(done, "conf-min3-day", _block(0.05, good_day_bull), _block(0.09, good_day_bear))
    _write(done, "conf-min4-day", _block(0.06, [0.09, 0.09, 0.09, 0.09, 0.03, 0.05]), _block(0.08, [0.08] * 6))
    _write(done, "conf-min5-day", _block(0.10, [0.1] * 6, n=300), _block(0.10, [0.1] * 6, n=300))
    # week: only min4 bullish qualifies -> one side only
    _write(done, "conf-min3-week", _block(0.01, [0.01] * 6), _block(0.01, [0.01] * 6))
    _write(done, "conf-min4-week", _block(0.04, [0.04] * 6), _block(0.03, [0.03, 0.03, 0.03, 0.03, 0.01, 0.03]))
    _write(done, "conf-min5-week", _block(-0.01, [-0.01] * 6), _block(-0.01, [-0.01] * 6))
    _write(done, "conf-min4-no-oi-day", _block(0.04, good_day_bull), _block(0.10, good_day_bear))
    t = rep.build(done)
    sel = {s["horizon"]: s for s in t["selections"]}
    assert sel["day"]["final"] and sel["day"]["counts_qualifying_on_both"] == [3]
    assert sel["day"]["tables"]["day_bullish"]["min_count"] == 3 and sel["day"]["tables"]["day_bearish"]["min_count"] == 3
    rows = {(r["table"], r["min_count"]): r for r in t["configs"]}
    assert rows[("day_bullish", 4)]["qualifies"] is False                 # 2019 equals the live rule, not above
    assert rows[("day_bullish", 5)]["rule"]["picks"] is False
    assert rows[("day_bearish", 4)]["passes_rule"] is True and rows[("day_bearish", 4)]["qualifies"] is True
    assert rows[("week_bullish", 4)]["qualifies"] and not rows[("week_bearish", 4)]["qualifies"]
    assert sel["week"]["tables"]["week_bullish"] == {"selected": "CONFLUENCE_MIN4", "min_count": 4,
                                                     "one_side_only": True, "fit_mean_pts": 4.0}
    assert sel["week"]["tables"]["week_bearish"]["selected"] is None
    abl = {(a["table"], a["dropped"]): a for a in t["ablations"]}
    assert abl[("day_bullish", "oi")]["minus_min4_pts"] == pytest.approx(-2.0)
    assert abl[("day_bearish", "oi")]["minus_min4_pts"] == pytest.approx(2.0)
    assert len(t["pending"]) == 20 - 7
    rep.render_md(t)
