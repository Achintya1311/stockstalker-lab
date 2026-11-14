"""Synthetic tests for a pick's checks (`picks/checks.py`) and how they ride on the picks payload."""

from __future__ import annotations

import re
from types import SimpleNamespace

import numpy as np
import pandas as pd

from picks.checks import LABELS, candidates_for, checks_for, trigger_of
from picks.select import pick_both_sides, pick_table
from strategies import champion_v1, t04_connors_rsi2
from strategies import composite_v2 as V2
from strategies import g_gates as G
from strategies.g_gates_audit import synthetic_panel
from tests._picks_dataset import make_dataset, trading_dates

BANNED = re.compile(r"\b(buy|sell|target|upside|entry|stop|risk|reward|p&l|profit|loss|return|gain)", re.I)


def _fake_t04(picks: dict[str, float]):
    """Looks like the T04 module to `trigger_of`, scores a fixed set of symbols."""
    return SimpleNamespace(
        __name__=t04_connors_rsi2.__name__,
        score=lambda h: pd.Series({s: v for s, v in picks.items() if s in set(h["symbol"])}, dtype=float),
        rules_fired=lambda h, s: "synthetic",
    )


def test_labels_cover_every_gate_in_plain_words():
    assert set(LABELS) == set(G.GATES)
    for label in LABELS.values():
        assert len(label.split()) <= 4 and not BANNED.search(label) and not re.search(r"\d", label)


def test_trigger_and_candidates_come_from_the_lab_mappings():
    assert trigger_of(t04_connors_rsi2) == "t04" and trigger_of("strategies.a01_weekly_reversal") == "a01"
    assert trigger_of(champion_v1) is None
    for table, trig in V2.TABLES.items():
        assert candidates_for(trig) == V2.CANDIDATES[table]


def test_shape_and_counts_on_a_panel():
    panel = synthetic_panel(n_symbols=12, n_rows=330)
    syms = sorted(panel["symbol"].unique())[:3]
    out = checks_for(panel, "strategies.e2a_a02_crowded", -1, syms)
    assert set(out) == set(syms)
    for s in syms:
        c = out[s]
        assert set(c) == {"checks", "checks_agree", "checks_total"}
        assert [r["k"] for r in c["checks"]] == list(V2.CANDIDATES["day_bearish"])
        for r in c["checks"]:
            assert set(r) == {"k", "label", "ok"} and r["label"] == LABELS[r["k"]] and r["ok"] in (True, False, None)
        assert c["checks_agree"] == sum(r["ok"] is True for r in c["checks"])
        assert c["checks_total"] == sum(r["ok"] is not None for r in c["checks"])
        assert 0 <= c["checks_agree"] <= c["checks_total"] <= len(c["checks"])
        # every verdict is the gate's own answer, asked with the trigger
        for r in c["checks"]:
            v = G.GATES[r["k"]](panel, {x: -1 for x in syms}, "e2a")
            assert r["ok"] == (v[s] if s in v else None)


def test_short_history_gives_null_not_false():
    dates = trading_dates(40)
    data = make_dataset({"AAA": 0.001, "BBB": -0.001}, dates)
    c = checks_for(data, t04_connors_rsi2, 1, ["AAA"])["AAA"]
    by = {r["k"]: r["ok"] for r in c["checks"]}
    assert by["g9"] is None and by["g10"] is None and by["g7"] is None  # under 252 / 200 rows, no OI
    assert c["checks_total"] == sum(v is not None for v in by.values()) < len(by)


def test_absent_when_trigger_unknown_or_on_the_other_side():
    panel = synthetic_panel(n_symbols=6, n_rows=80)
    syms = list(panel["symbol"].unique()[:2])
    assert checks_for(panel, champion_v1, 1, syms) == {}
    assert checks_for(panel, "strategies.t04_connors_rsi2", -1, syms) == {}
    assert checks_for(panel, t04_connors_rsi2, 1, []) == {}


def test_payload_carries_checks_for_a_trigger_table_and_leaves_them_out_otherwise():
    dates = trading_dates(champion_v1.MIN_ROWS + 10)
    data = make_dataset({"UP": 0.01, "DOWN": -0.01, "FLAT": 0.0}, dates)
    asof, session = dates[-2], dates[-1]
    bull, bear, _ = pick_both_sides(data, (_fake_t04({"FLAT": 1.0}), "t04_connors_rsi2@v1"), (champion_v1, "champion_v1@v1"), session, asof)
    assert [p["symbol"] for p in bull] == ["FLAT"]
    p = bull[0]
    assert [r["k"] for r in p["checks"]] == list(V2.CANDIDATES["day_bullish"])
    assert p["checks_agree"] == sum(r["ok"] is True for r in p["checks"])
    assert p["checks_total"] == sum(r["ok"] is not None for r in p["checks"])
    assert bear and all(not {"checks", "checks_agree", "checks_total"} & set(q) for q in bear)


def test_checks_use_only_the_history_the_pick_was_made_from():
    dates = trading_dates(champion_v1.MIN_ROWS + 30)
    rng = np.random.default_rng(1)
    data = make_dataset({"AAA": 0.002, "BBB": -0.001, "CCC": 0.0}, dates)
    data["close"] = data["close"] * (1 + rng.normal(0, 0.01, len(data)))
    session, asof = dates[-20], dates[-21]
    fake = _fake_t04({"AAA": 1.0})
    a = pick_table(data, fake, "t04_connors_rsi2@v1", session, 1, asof)
    future = data.copy()
    future.loc[future["date"] >= session, "volume"] *= 50
    future.loc[future["date"] >= session, "close"] *= 1.3
    b = pick_table(future, fake, "t04_connors_rsi2@v1", session, 1, asof)
    assert a[0]["checks"] == b[0]["checks"]
