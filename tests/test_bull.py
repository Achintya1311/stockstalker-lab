"""Synthetic tests for the BULL_V1 rules (`strategies/bull_core.py`): B1 trend cross, B4A put writing, B4B end of
long liquidation, B5 failed bearish setup; plus their audit, held replays, cards and catalog rows.

For every rule, on hand-built series: it fires on the session it should; it does NOT fire one bar early (the same
series without the signal session); a row after the signal session is never read; and missing open interest makes
the symbol abstain rather than fire.
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

from engine.exits import parse_exit_plan
from engine.replay import truncate
from strategies import a02_extreme_day_reversal as a02
from strategies import bull_core as C
from strategies import e2a_a02_crowded, e2b_a02_uncrowded
from strategies.bull_audit import panel as audit_panel
from strategies.bull_audit import run_all
from tests.test_reasoning_no_price_levels import LEVEL

ROOT = Path(__file__).resolve().parent.parent
HELD = ROOT / "experiments" / "held" / "bull"
PENDING = ROOT / "experiments" / "pending"
DONE = ROOT / "experiments" / "done"
CATALOG = ROOT / "cards" / "catalog.csv"
CARD_IDS = {"b1_trend_cross": "B1", "b4_put_writing": "B4A", "b4_long_liquidation_end": "B4B",
            "b5_failed_bearish": "B5"}
TRAIL = {"kind": "trail", "stop_atr": 3, "max_sessions": 20, "sides": ["bullish"]}
EXPERIMENTS = {  # id -> (module, horizon, folder, exit block or None)
    "b1-trend-cross-trail-day": ("b1_trend_cross", "day", "day", TRAIL),
    "b4-put-writing-day": ("b4_put_writing", "day", "day", None),
    "b4-long-liquidation-end-day": ("b4_long_liquidation_end", "day", "day", None),
    "b5-failed-bearish-day": ("b5_failed_bearish", "day", "day", None),
    "b1-trend-cross-trail-week": ("b1_trend_cross", "week", "week_month", TRAIL),
    "b5-failed-bearish-week": ("b5_failed_bearish", "week", "week_month", None),
}
LIVE_MODULES = {"t04_connors_rsi2", "e2a_a02_crowded", "composite_v1_day_bearish", "a05b_max_effect_ranked",
                "a01_weekly_reversal"}


def frame(closes, symbol: str = "AAA", start: str = "2016-01-01", **cols) -> pd.DataFrame:
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    n = len(c)
    df = pd.DataFrame({
        "date": pd.bdate_range(start, periods=n).strftime("%Y-%m-%d"),
        "symbol": symbol, "open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998,
        "close": c, "prevclose": np.r_[c[0], c[:-1]], "volume": 1e6, "has_future": True,
        "oi_futstk": 100_000.0, "oi_chg_futstk": 100.0,
    })
    for k, v in cols.items():
        df[k] = v
    return df


def with_next_row(h: pd.DataFrame, **override) -> pd.DataFrame:
    """`h` plus one wild row after its last session (what a lookahead would read)."""
    last = h.iloc[-1].copy()
    last["date"] = (pd.Timestamp(last["date"]) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")
    for col in ("open", "high", "low", "close"):
        last[col] = last[col] * 5.0
    last["prevclose"] = h.iloc[-1]["close"]
    for k, v in override.items():
        last[k] = v
    return pd.concat([h, last.to_frame().T.astype(h.dtypes.to_dict())], ignore_index=True)


def no_lookahead(name: str, h: pd.DataFrame) -> bool:
    nxt = with_next_row(h)
    return C.rule_score(name, truncate(nxt, nxt["date"].iloc[-1])).sort_index().equals(
        C.rule_score(name, h).sort_index())


# ---------------------------------------------------------------- B1


def b1_closes() -> list[float]:
    """A long rise (close well above the 200-day), a pullback that puts EMA20 under EMA50, then a recovery."""
    up = list(np.linspace(100, 160, 230))
    down = list(np.linspace(160, 140, 30)[1:])
    rec = list(np.linspace(140, 175, 40)[1:])
    return up + down + rec


def first_fire(closes, name: str = "b1_trend_cross", start: int = 230) -> int:
    for k in range(start, len(closes)):
        if C.rule_score(name, frame(closes[: k + 1])).get("AAA") is not None:
            return k
    raise AssertionError("never fired")


def test_b1_fires_on_the_cross_session_not_a_bar_early_or_late():
    c = b1_closes()
    k = first_fire(c)
    tail = pd.Series(c[: k + 1][-C.G.TAIL_DATES:])   # the rule sees the last 250 sessions; EMAs start there
    e20 = tail.ewm(span=20, adjust=False).mean()
    e50 = tail.ewm(span=50, adjust=False).mean()
    # independent check: the cross is on session k
    assert e20.iloc[-1] > e50.iloc[-1] and e20.iloc[-2] <= e50.iloc[-2]
    assert c[k] > np.mean(c[k - 199: k + 1])
    assert C.rule_score("b1_trend_cross", frame(c[:k])).empty           # one bar early
    assert C.rule_score("b1_trend_cross", frame(c[: k + 2])).empty      # next bar: cross is old
    h = frame(c[: k + 1])
    o, hi, lo, cl = (h[x].to_numpy()[-C.G.TAIL_DATES:] for x in ("open", "high", "low", "close"))
    atr = C.G.atr(hi, lo, cl)[-1]
    assert C.rule_score("b1_trend_cross", h)["AAA"] == pytest.approx((e20.iloc[-1] - e50.iloc[-1]) / atr)
    assert no_lookahead("b1_trend_cross", h)


def test_b1_needs_close_above_the_200_day():
    # the same dip-and-recover shape, but after a long FALL: EMA20 crosses EMA50 below the 200-day average
    down = list(np.linspace(200, 120, 230))
    dip = list(np.linspace(120, 110, 30)[1:])
    rec = list(np.linspace(110, 125, 25)[1:])
    c = down + dip + rec
    for k in range(230, len(c)):
        assert C.rule_score("b1_trend_cross", frame(c[: k + 1])).empty


def test_b1_needs_200_rows():
    c = b1_closes()
    k = first_fire(c)
    assert C.rule_score("b1_trend_cross", frame(c[k - 150: k + 1])).empty


def test_b1_symbol_without_future_on_last_date_is_not_judged():
    c = b1_closes()
    h = frame(c[: first_fire(c) + 1])
    h.loc[h.index[-1], "has_future"] = False
    assert C.rule_score("b1_trend_cross", h).empty


# ---------------------------------------------------------------- B4A


def b4a_history(close_s=103.0, ce=(10_000.0, 11_000.0), pe=(8_000.0, 10_000.0), expiry=("2016-01-28", "2016-01-28")):
    h = frame([100.0, 100.0, close_s])
    h["oi_ce_optstk"] = [10_000.0, ce[0], ce[1]]
    h["oi_pe_optstk"] = [8_000.0, pe[0], pe[1]]
    h["expiry_futstk"] = ["2016-01-28", expiry[0], expiry[1]]
    return h


def test_b4a_fires_on_an_up_day_with_put_oi_rising_faster():
    h = b4a_history()   # put +25%, call +10%, close +3%
    s = C.rule_score("b4_put_writing", h)
    assert s["AAA"] == pytest.approx(0.25 - 0.10)
    assert C.rule_score("b4_put_writing", h.iloc[:-1]).empty            # one bar early
    assert no_lookahead("b4_put_writing", h)


@pytest.mark.parametrize("kw", [
    {"close_s": 99.0},                                       # down day
    {"close_s": 100.0},                                      # flat day
    {"pe": (8_000.0, 8_400.0)},                              # put +5% < call +10%
    {"ce": (10_000.0, 9_000.0), "pe": (8_000.0, 7_900.0)},   # put fell (even though by less than call)
    {"expiry": ("2016-01-28", "2016-02-25")},                # expiry roll: near-month option OI resets
])
def test_b4a_abstains_when_a_condition_fails(kw):
    assert C.rule_score("b4_put_writing", b4a_history(**kw)).empty


@pytest.mark.parametrize("col,idx,val", [
    ("oi_ce_optstk", 1, np.nan), ("oi_pe_optstk", 1, np.nan),    # missing on the prior session
    ("oi_ce_optstk", 1, 0.0), ("oi_pe_optstk", 1, 0.0),          # not positive on the prior session
    ("oi_ce_optstk", 2, np.nan), ("oi_pe_optstk", 2, np.nan),    # missing on the signal session
])
def test_b4a_missing_or_zero_oi_abstains(col, idx, val):
    h = b4a_history()
    h.loc[idx, col] = val
    assert C.rule_score("b4_put_writing", h).empty
    assert "abstain" in importlib.import_module("strategies.b4_put_writing").rules_fired(h, "AAA")


def test_b4a_no_option_columns_or_missing_prior_session():
    assert C.rule_score("b4_put_writing", frame([100.0, 101.0, 103.0])).empty
    h = b4a_history()
    other = frame([50.0], symbol="ZZZ", start=h["date"].iloc[1])   # ZZZ trades on S-1, AAA does not
    other["oi_ce_optstk"], other["oi_pe_optstk"], other["expiry_futstk"] = 1.0, 1.0, "2016-01-28"
    gap = pd.concat([h.drop(index=1), other], ignore_index=True)
    assert "AAA" not in C.rule_score("b4_put_writing", gap).index


def test_b4a_up_day_uses_the_adjusted_base():
    # a 1:2 split on S: the raw close halves, but PREVCLOSE (the exchange's adjusted base) shows an up session
    h = b4a_history(close_s=51.5)
    h.loc[2, "prevclose"] = 50.0
    assert C.rule_score("b4_put_writing", h)["AAA"] == pytest.approx(0.15)


# ---------------------------------------------------------------- B4B


def quiet(n: int = 30, base: float = 100.0) -> list[float]:
    """Alternating +-0.5% closes: a small, nonzero trailing sigma."""
    out = [base]
    for i in range(n - 1):
        out.append(out[-1] * (1.005 if i % 2 == 0 else 0.995))
    return out


def b4b_history(move: float = -0.05, oi_chg: float = -500.0) -> pd.DataFrame:
    c = quiet()
    c.append(c[-1] * (1 + move))
    h = frame(c)
    h.loc[h.index[-1], "oi_chg_futstk"] = oi_chg
    return h


def test_b4b_fires_on_extreme_down_day_with_falling_oi():
    h = b4b_history()
    s = C.rule_score("b4_long_liquidation_end", h)
    assert s["AAA"] == pytest.approx(a02.score(h)["AAA"]) and s["AAA"] > 2.0
    assert C.rule_score("b4_long_liquidation_end", h.iloc[:-1]).empty    # one bar early
    assert no_lookahead("b4_long_liquidation_end", h)


@pytest.mark.parametrize("move,oi", [(-0.05, 500.0), (-0.05, 0.0), (0.05, -500.0), (-0.004, -500.0)])
def test_b4b_abstains(move, oi):
    # OI rose (E2A's bullish arm), OI flat, an extreme UP day, an ordinary down day
    assert C.rule_score("b4_long_liquidation_end", b4b_history(move, oi)).empty


def test_b4b_missing_futures_oi_abstains():
    h = b4b_history()
    h.loc[h.index[-1], "oi_chg_futstk"] = np.nan
    assert C.rule_score("b4_long_liquidation_end", h).empty
    assert C.rule_score("b4_long_liquidation_end", h.drop(columns=["oi_chg_futstk"])).empty


def test_b4b_is_e2a_mirrored_and_e2b_bullish_without_flat_oi():
    p = audit_panel()
    for d in sorted(p["date"].unique())[-40:]:
        h = truncate(p, d)
        mine = C.rule_score("b4_long_liquidation_end", h)
        e2b = e2b_a02_uncrowded.score(h)
        chg = h.sort_values("date").groupby("symbol").tail(1).set_index("symbol")["oi_chg_futstk"]
        expect = e2b[(e2b > 0) & (chg.reindex(e2b.index) < 0)]
        assert mine.sort_index().equals(expect.sort_index().astype(float))
        # never overlaps E2A's bullish arm (OI rose)
        assert not set(mine.index) & set(e2a_a02_crowded.score(h).loc[lambda s: s > 0].index)


# ---------------------------------------------------------------- B5


def b5_history(after=(0.0, 0.002, 0.001), oi_chg: float = 800.0, jump: float = 0.05) -> pd.DataFrame:
    """Quiet closes, then an extreme UP day with OI rising (E2A bearish) at T3, then three more sessions whose
    closes move by `after` (cumulative, relative to the T3 close)."""
    c = quiet()
    c.append(c[-1] * (1 + jump))
    ref = c[-1]
    c += [ref * (1 + a) for a in after]
    h = frame(c)
    h.loc[h.index[-1 - len(after)], "oi_chg_futstk"] = oi_chg
    return h


def test_b5_fires_three_sessions_after_a_failed_e2a_setup():
    h = b5_history()
    t3 = h["date"].iloc[-4]
    assert e2a_a02_crowded.score(h[h["date"] <= t3])["AAA"] < 0           # E2A bearish setup on T3
    assert C.e2a_bearish_on(h, t3).keys() == {"AAA"}
    s = C.rule_score("b5_failed_bearish", h)
    o, hi, lo, cl = (h[x].to_numpy() for x in ("open", "high", "low", "close"))
    assert s["AAA"] == pytest.approx((cl[-1] - cl[-4]) / C.G.atr(hi, lo, cl)[-1])
    assert C.rule_score("b5_failed_bearish", h.iloc[:-1]).empty            # one bar early (T3 is then S-2)
    assert no_lookahead("b5_failed_bearish", h)


def test_b5_equal_close_counts_and_ranks_last():
    h = b5_history(after=(-0.01, 0.01, 0.0))
    assert C.rule_score("b5_failed_bearish", h)["AAA"] == pytest.approx(C.B5_FLOOR)


@pytest.mark.parametrize("kw", [
    {"after": (0.0, 0.0, -0.001)},          # it did fall: close below the T3 close
    {"oi_chg": -800.0},                     # OI fell on T3: not E2A's setup
    {"jump": 0.004},                        # no extreme day on T3
    {"jump": -0.05},                        # extreme DOWN day: E2A bullish, not its bearish setup
    {"after": (0.0, 0.01, 0.02, 0.03)},     # setup now 4 sessions back
])
def test_b5_abstains(kw):
    assert C.rule_score("b5_failed_bearish", b5_history(**kw)).empty


def test_b5_missing_futures_oi_on_setup_day_abstains():
    h = b5_history()
    h.loc[h.index[-4], "oi_chg_futstk"] = np.nan
    assert C.rule_score("b5_failed_bearish", h).empty


def test_b5_symbol_without_a_row_on_t3_abstains():
    h = b5_history()
    t3 = h["date"].iloc[-4]
    other = frame(quiet(len(h)), symbol="ZZZ")
    gap = pd.concat([h[h["date"] != t3], other], ignore_index=True)   # AAA skips T3; ZZZ keeps the calendar
    assert "AAA" not in C.rule_score("b5_failed_bearish", gap).index


def test_b5_e2a_window_matches_full_history():
    p = audit_panel()
    dates = sorted(p["date"].unique())
    for d in dates[-30:]:
        full = e2a_a02_crowded.score(p[p["date"] <= d])
        full = {s: float(v) for s, v in full.items() if v < 0}
        assert C.e2a_bearish_on(p, d) == full


# ---------------------------------------------------------------- audit, modules, ymls, cards, catalog


def test_audit_passes_and_every_rule_fires_on_the_panel():
    result = run_all()
    assert result["passed"], result
    assert all(n > 0 for n in result["strength_positive"]["picks"].values()), result


def test_thin_modules_match_core_and_reasoning_is_safe():
    p = audit_panel()
    h = truncate(p, sorted(p["date"].unique())[-1])
    signals = {"b1_trend_cross": frame(b1_closes()[: first_fire(b1_closes()) + 1]),
               "b4_put_writing": b4a_history(), "b4_long_liquidation_end": b4b_history(),
               "b5_failed_bearish": b5_history()}
    for name in C.RULES:
        mod = importlib.import_module(f"strategies.{name}")
        assert mod.score(h).sort_index().equals(C.rule_score(name, h).sort_index())
        for s in list(h["symbol"].unique()) + ["AAA"]:
            for hist in (h, signals[name]):
                text = mod.rules_fired(hist, s)
                assert text.startswith(name.upper())
                assert not any(w in text.lower() for w in ("buy", "sell", "target", "stop", "entry"))
                assert not LEVEL.search(text)
        text = mod.rules_fired(signals[name], "AAA")
        assert "bullish pick" in text, (name, text)
        assert "abstain" in mod.rules_fired(signals[name].iloc[:-1], "AAA")
        assert (mod.score(signals[name]) > 0).all()


def test_held_replays_in_bull_folders_train_only():
    # A yml sits in held/bull/<day|week_month>/, then pending/ once queued, then is gone when done/<id> exists.
    for eid, (module, horizon, folder, exit_block) in EXPERIMENTS.items():
        assert module not in LIVE_MODULES
        paths = [q for q in (HELD / folder / f"{eid}.yml", PENDING / f"{eid}.yml") if q.exists()]
        assert len(paths) <= 1, eid
        if not paths:
            assert (DONE / eid).exists(), eid
            continue
        exp = yaml.safe_load(paths[0].read_text())
        expect = {"id": eid, "strategy": f"strategies.{module}", "split": "train", "horizon": horizon,
                  "dates": {"start": "2015-01-01", "end": "2020-12-31"}}
        if exit_block:
            expect["exit"] = exit_block
            assert parse_exit_plan(exp["exit"])["sides"] == ["bullish"]
        assert exp == expect, eid
    for p in HELD.rglob("*.yml"):
        # b2- / b3- ymls (opt-in yardstick / top_n) are checked in tests/test_scoring_options.py
        assert (p.stem in EXPERIMENTS or p.stem.startswith(("b2-", "b3-"))) and "validation" not in p.stem
        assert yaml.safe_load(p.read_text())["split"] == "train"


def test_cards_and_catalog_rows():
    rows = {r["id"]: r for r in csv.DictReader(CATALOG.open(newline=""))}
    for name, cid in CARD_IDS.items():
        card = yaml.safe_load((ROOT / "cards" / f"{cid}.yml").read_text())
        for field in ("source_url", "author", "license", "published_on", "claim_as_stated", "horizon",
                      "rules_plain", "params", "red_flags", "status", "assumptions"):
            assert field in card, (cid, field)
        text = json.dumps(card).lower()
        assert "one fixed parameter set" in text
        assert not any(f" {w} " in text for w in ("buy", "sell", "target", "entry", "stop-loss"))
        assert card["status"].startswith("held")
        assert cid in rows and rows[cid]["status"].startswith("held")
    assert len(rows) >= 240
