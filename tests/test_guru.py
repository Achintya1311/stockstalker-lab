"""Synthetic tests for the GURU_V1 setups (`strategies/guru_core.py`), their audit, held replays, cards, catalog
rows and report.

For every setup, on hand-built bars: it fires on the session it should, with the expected side; it does NOT fire
one bar early (the same bars without the signal session); the mirror image (prices flipped about a level) fires
on the other side with the same strength; and the panel-level score never reads past the last visible session.
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
from scripts import guru_report as rep
from strategies import guru_core as C
from strategies.guru_audit import run_all
from strategies.g_gates_audit import synthetic_panel
from tests.test_reasoning_no_price_levels import LEVEL

ROOT = Path(__file__).resolve().parent.parent
HELD = ROOT / "experiments" / "held" / "guru"
PENDING = ROOT / "experiments" / "pending"
DONE = ROOT / "experiments" / "done"
CATALOG = ROOT / "cards" / "catalog.csv"


# ---------------------------------------------------------------- hand-built bars


def from_closes(c, spread: float = 0.5):
    c = np.asarray(c, dtype=float)
    o = np.r_[c[0], c[:-1]]
    return o, np.maximum(o, c) + spread, np.minimum(o, c) - spread, c


def flat(n: int = 70):
    """Quiet bars: open 100, high 101, low 99, close 100.2 (range 2, ATR 2)."""
    return np.full(n, 100.0), np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.2)


def put(bars, i: int, o, h, l, c):
    out = tuple(x.copy() for x in bars)
    for arr, v in zip(out, (o, h, l, c)):
        arr[i] = v
    return out


def append(bars, o, h, l, c):
    return tuple(np.r_[x, v] for x, v in zip(bars, (o, h, l, c)))


def drop_last(bars):
    return tuple(x[:-1] for x in bars)


def flip(bars, level: float = 200.0):
    return C.flip(*bars, level=level)


def history_from(bars, symbol: str = "AAA") -> pd.DataFrame:
    o, h, l, c = bars
    n = len(c)
    return pd.DataFrame({
        "date": pd.bdate_range("2016-01-01", periods=n).strftime("%Y-%m-%d"),
        "symbol": symbol, "open": o, "high": h, "low": l, "close": c,
        "prevclose": np.r_[c[0], c[:-1]], "volume": 1e6, "has_future": True,
    })


# Holy Grail: a quiet base, a steady rise (ADX high and rising, +DI > -DI), one session falling through the
# 20 EMA (the touch), then a session trading above the touch session's high.
def hg_setup():
    c = [100 + 0.3 * (-1) ** i for i in range(40)]
    for _ in range(30):
        c.append(c[-1] + 1.0)
    c.append(c[-1] - 12)          # touch
    return from_closes(c)


def hg_signal():
    b = hg_setup()
    top = b[1][-1]                                   # the touch session's high
    return append(b, top - 0.2, top + 1.5, top - 0.6, top + 1.0)   # opens high, clear of the 20 EMA


# Turtle Soup: a single deeper low 8 sessions back (the previous 20-session low), then a session undercutting
# it and closing back above it.
def ts_base():
    return put(flat(), 61, 100.0, 101.0, 97.0, 100.2)


def ts_signal():
    return append(ts_base(), 99.0, 99.5, 96.0, 98.0)


# Turtle Soup Plus One: the new low session closes below the previous low; the next session closes above it.
def ts1_setup():
    return append(ts_base(), 99.0, 99.2, 96.0, 96.5)


def ts1_signal():
    return append(ts1_setup(), 96.6, 98.6, 96.4, 98.2)


# 80-20: a session opening at its top and closing at its bottom, then one undercutting its low and closing above.
def et_setup():
    return append(flat(), 100.9, 101.0, 99.0, 99.2)


def et_signal():
    return append(et_setup(), 99.1, 99.8, 98.5, 99.5)


# Five-EMA: a session wholly below its 5 EMA after a drop, then one trading above its high.
def fe_setup():
    return append(flat(), 96.0, 97.0, 95.0, 95.5)


def fe_signal():
    return append(fe_setup(), 95.6, 97.5, 95.4, 97.2)


# Bollinger 1.5: a session wholly below the lower 1.5 sd band, then one trading above its high.
def bb_setup():
    b = flat()
    b = (b[0], b[1], b[2], np.array([100.2 + 0.3 * (-1) ** i for i in range(len(b[3]))]))
    return append(b, 97.0, 97.5, 96.5, 97.0)


def bb_signal():
    return append(bb_setup(), 97.1, 98.0, 96.9, 97.8)


# Anti: a long rise that lifts the slow line, a two-session dip in the fast line, then a turn up.
def anti_closes():
    c = [100.0] * 30
    for i in range(32):
        c.append(c[-1] + 0.2 + 0.03 * i)
    c.append(c[-1] - 0.4)
    c.append(c[-1] - 0.3)
    return c


def anti_setup():
    return from_closes(anti_closes())


def anti_signal():
    c = anti_closes()
    return from_closes(c + [c[-1] + 6.0])


CASES = {
    "r01_holy_grail": (hg_signal, C.holy_grail),
    "r02_turtle_soup": (ts_signal, C.turtle_soup),
    "r02b_turtle_soup_plus_one": (ts1_signal, C.turtle_soup_plus_one),
    "r03_anti": (anti_signal, C.anti),
    "r04_eighty_twenty": (et_signal, C.eighty_twenty),
    "p01_five_ema": (fe_signal, C.five_ema),
    "p02_bollinger_1p5": (bb_signal, C.bollinger_1p5),
}


# ---------------------------------------------------------------- each setup: fires, not one bar early, mirror


@pytest.mark.parametrize("name", list(CASES))
def test_fires_bullish_on_the_signal_session(name):
    make, fn = CASES[name]
    hit = fn(*make())
    assert hit is not None, name
    side, strength, note = hit
    assert side == 1 and strength > 0 and np.isfinite(strength)
    assert not LEVEL.search(note)


@pytest.mark.parametrize("name", list(CASES))
def test_does_not_fire_one_bar_early(name):
    make, fn = CASES[name]
    assert fn(*drop_last(make())) is None


@pytest.mark.parametrize("name", list(CASES))
def test_mirror_fires_bearish_with_the_same_strength(name):
    make, fn = CASES[name]
    side, strength, _ = fn(*make())
    m_side, m_strength, _ = fn(*flip(make()))
    assert m_side == -side
    assert m_strength == pytest.approx(strength, rel=1e-9)


@pytest.mark.parametrize("name", list(CASES))
def test_panel_score_sign_and_mirror(name):
    make, fn = CASES[name]
    side, strength, _ = fn(*make())
    up = C.config_score(name, history_from(make(), "UPP"))
    dn = C.config_score(name, history_from(flip(make()), "DNN"))
    assert up["UPP"] == pytest.approx(side * strength)
    assert dn["DNN"] == pytest.approx(-side * strength)


@pytest.mark.parametrize("name", list(CASES))
def test_no_lookahead_extra_future_rows_change_nothing(name):
    make, _ = CASES[name]
    h = history_from(make())
    last = h["date"].max()
    future = history_from(append(make(), 1.0, 900.0, 0.5, 450.0))   # wild extra session after the signal
    extra = future["date"].max()
    assert extra > last
    viewed = truncate(future, extra)                                 # what the engine hands over on that date
    assert C.config_score(name, viewed).equals(C.config_score(name, h))


@pytest.mark.parametrize("name", list(CASES))
def test_short_history_abstains(name):
    make, fn = CASES[name]
    b = make()
    assert fn(*tuple(x[-(C.MIN_ROWS - 1):] for x in b)) is None


# ---------------------------------------------------------------- rule details


def test_holy_grail_needs_adx_trend_before_the_touch():
    # The same touch and break after a quiet, trendless base (no ADX > 30 rising): no signal.
    c = [100 + 0.3 * (-1) ** i for i in range(70)]
    c += [c[-1] - 3, c[-1] + 3]
    assert C.holy_grail(*from_closes(c)) is None


def test_holy_grail_signal_is_the_first_break_only():
    # A second break after the first is not a new signal.
    b = hg_signal()
    top = b[1][-1]
    assert C.holy_grail(*append(b, top - 0.2, top + 1.0, top - 0.5, top + 0.5)) is None


def test_turtle_soup_needs_the_prior_low_four_sessions_back():
    b = put(flat(), 68, 100.0, 101.0, 97.0, 100.2)   # previous low only 2 sessions before the signal session
    assert C.turtle_soup(*append(b, 99.0, 99.5, 96.0, 98.0)) is None
    b = put(flat(), 66, 100.0, 101.0, 97.0, 100.2)   # exactly 4 sessions before: fires
    assert C.turtle_soup(*append(b, 99.0, 99.5, 96.0, 98.0))[0] == 1


def test_turtle_soup_needs_the_close_back_above():
    assert C.turtle_soup(*append(ts_base(), 99.0, 99.5, 96.0, 96.8)) is None


def test_turtle_soup_depth_in_atr_units():
    b = ts_signal()
    _, strength, _ = C.turtle_soup(*b)
    assert strength == pytest.approx(1.0 / C.atr(b[1], b[2], b[3])[-1])


def test_turtle_soup_and_plus_one_do_not_fire_on_the_same_session():
    assert C.turtle_soup(*ts1_signal()) is None
    assert C.turtle_soup_plus_one(*ts_signal()) is None


def test_eighty_twenty_needs_the_extreme_bar():
    b = append(flat(), 100.5, 101.0, 99.0, 99.2)       # opened mid-range: not an 80-20 bar
    assert C.eighty_twenty(*append(b, 99.1, 99.8, 98.5, 99.5)) is None


def test_five_ema_alert_candle_must_be_wholly_clear():
    b = append(flat(), 96.0, 99.9, 95.0, 95.5)          # high reaches back above the 5 EMA
    assert C.five_ema(*append(b, 95.6, 100.5, 95.4, 97.2)) is None


def test_bollinger_band_is_1p5_population_sd():
    b = bb_setup()
    s = pd.Series(b[3])
    lower = s.rolling(20).mean().iloc[-1] - 1.5 * s.rolling(20).std(ddof=0).iloc[-1]
    _, strength, _ = C.bollinger_1p5(*bb_signal())
    assert strength == pytest.approx((lower - b[1][-1]) / C.atr(b[1], b[2], b[3])[-1])


def test_anti_lines_on_the_signal_session():
    c = np.array(anti_closes() + [anti_closes()[-1] + 6.0])
    fast = C.sma(c, 3) - C.sma(c, 10)
    slow = C.sma(fast, 16)
    assert slow[-1] > slow[-2] > slow[-3] > slow[-4]
    assert fast[-4] > fast[-3] > fast[-2] < fast[-1]


def test_adx_matches_t15():
    from strategies.t15_adx_regime import _adx_latest
    p = synthetic_panel(n_symbols=1, n_rows=200)
    h, l, c = (p[k].to_numpy() for k in ("high", "low", "close"))
    assert C.adx(h, l, c)[2][-1] == pytest.approx(_adx_latest(h, l, c, 14), rel=1e-9)


def test_both_sides_at_once_abstains():
    assert C._one([(1, 1.0, "a"), (-1, 1.0, "b")]) is None


def test_symbol_without_future_on_last_date_is_not_judged():
    h = history_from(ts_signal())
    h.loc[h.index[-1], "has_future"] = False
    assert C.config_score("r02_turtle_soup", h).empty


def test_empty_history():
    assert C.config_score("r01_holy_grail", synthetic_panel().iloc[0:0]).empty


def test_audit_passes():
    result = run_all()
    assert result["passed"], result


# ---------------------------------------------------------------- modules, held replays, cards, catalog


def test_thin_modules_match_configs_and_reasoning_is_safe():
    panel = synthetic_panel()
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    signal = history_from(ts_signal(), "TSX")
    for name, cfg in C.CONFIGS.items():
        mod = importlib.import_module(f"strategies.{name}")
        assert mod.score(h).sort_index().equals(C.config_score(name, h).sort_index())
        for s in list(h["symbol"].unique()):
            text = mod.rules_fired(h, s)
            assert text.startswith(name.upper())
            assert not any(w in text.lower() for w in ("buy", "sell", "target", "stop", "entry"))
            assert not LEVEL.search(text)
    text = importlib.import_module("strategies.r02_turtle_soup").rules_fired(signal, "TSX")
    assert "bullish pick" in text


def test_held_replays_in_day_and_week_folders_and_none_validation():
    # A replay yml sits in held/guru/<day|week>/, then pending/ once queued, and is removed when its result is in done/.
    assert len(rep.EXPERIMENTS) == 2 * len(C.CONFIGS)
    for eid, (name, horizon) in rep.EXPERIMENTS.items():
        paths = [q for q in (HELD / horizon / f"{eid}.yml", PENDING / f"{eid}.yml") if q.exists()]
        if not paths:
            assert (DONE / eid).exists(), eid
            continue
        assert yaml.safe_load(paths[0].read_text()) == {
            "id": eid, "strategy": f"strategies.{name}", "split": "train", "horizon": horizon,
            "dates": {"start": "2015-01-01", "end": "2020-12-31"}}
    for p in HELD.rglob("*.yml"):
        assert "validation" not in p.stem and yaml.safe_load(p.read_text())["split"] == "train"


def test_cards_and_catalog_rows():
    rows = {r["id"]: r for r in csv.DictReader(CATALOG.open(newline=""))}
    for name, cfg in C.CONFIGS.items():
        card = yaml.safe_load((ROOT / "cards" / f"{cfg.config_id}.yml").read_text())
        for field in ("source_url", "author", "license", "published_on", "claim_as_stated", "horizon",
                      "rules_plain", "params", "red_flags", "status", "assumptions"):
            assert field in card, (cfg.config_id, field)
        assert card["assumptions"] and card["status"].startswith("held")
        text = json.dumps(card).lower()
        assert not any(f" {w} " in text for w in ("buy", "sell", "target", "entry", "stop-loss"))
        assert cfg.config_id in rows and rows[cfg.config_id]["status"] == "held"
    assert "daily adaptation" in json.dumps(yaml.safe_load((ROOT / "cards" / "P01.yml").read_text())).lower()
    assert sum(1 for _ in csv.reader(CATALOG.open(newline=""))) >= 232 + len(C.CONFIGS)


# ---------------------------------------------------------------- report


def test_report_runs_with_nothing_done(tmp_path, capsys):
    t = rep.build(tmp_path)
    assert t["rows"] == [] and len(t["pending"]) == len(rep.EXPERIMENTS)
    md = rep.render_md(t)
    assert "not run yet" in md
    assert rep.main(["--done", str(tmp_path), "--md", str(tmp_path / "g.md")]) == 0
    assert "not run yet" in capsys.readouterr().out
    assert (tmp_path / "g.md").exists()


def _block(edge: float, years: list[float], n: int = 600, t: float = 2.0) -> dict:
    return {"n_picks": n, "n_dates": 300, "coverage": 0.8, "accuracy": 0.5 + edge, "market_line": 0.5,
            "edge": edge, "edge_t": t, "directional_move": 0.001,
            "by_year": [{"year": 2015 + i, "edge": e} for i, e in enumerate(years)]}


def _write(done: Path, eid: str, bull: dict, bear: dict, dates=("2015-01-05", "2020-12-28")) -> None:
    (done / eid).mkdir(parents=True)
    (done / eid / "results.json").write_text(json.dumps(
        {"id": eid, "split": "train", "selections": {"top": {"bullish": bull, "bearish": bear}}}))
    (done / eid / "picks.json").write_text(json.dumps(
        [{"date": dates[0], "symbol": "X", "score": 1.0}, {"date": dates[1], "symbol": "Y", "score": -1.0}]))


def test_report_rows_and_live_rule(tmp_path):
    _write(tmp_path, "t04-connors-rsi2-day", _block(0.0337, [0.03] * 6), {"n_picks": 0})
    _write(tmp_path, "r02-turtle-soup-day", _block(0.04, [0.04, -0.01, 0.02, 0.03, 0.01, 0.05], t=2.0),
           _block(-0.01, [-0.01] * 6, t=-0.5))
    t = rep.build(tmp_path)
    rows = {(r["module"], r["table"]): r for r in t["rows"]}
    bull = rows[("r02_turtle_soup", "day_bullish")]
    assert bull["edge_pts"] == pytest.approx(4.0)
    assert bull["edge_ci95_pts"] == pytest.approx([4.0 - 1.96 * 2.0, 4.0 + 1.96 * 2.0])
    assert bull["years_positive"] == "5/6" and bull["picks_per_date"] == pytest.approx(2.0)
    assert bull["first_date"] == "2015-01-05" and bull["last_date"] == "2020-12-28"
    assert bull["live_edge_pts"] == pytest.approx(3.37) and bull["edge_minus_live_pts"] == pytest.approx(0.63)
    assert rows[("r02_turtle_soup", "day_bearish")]["live_edge_pts"] is None   # e2a replay not in this folder
    assert len(t["pending"]) == len(rep.EXPERIMENTS) - 1
    md = rep.render_md(t)
    assert "R02" in md and "T04" in md.upper()
