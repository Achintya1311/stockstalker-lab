"""COMPOSITE_V2: a train-split search over other ways to combine the C1 gates (`cards/COMPOSITE_V2.yml`).

COMPOSITE_V1 (trigger AND every qualifying gate) over-fit: on unseen data the hard AND failed on both bullish
tables. COMPOSITE_V2 tries three softer or re-thresholded families, each defined by HORIZON, not by table: a
setting is built for both the bullish and the bearish table of its horizon (day: T04 and E2A; week: A05B and
A01) wherever its gate exists for both triggers, and the pair shares one config key (`<horizon>_<setting>`)
so a report can score a setting on both sides.

Candidate gates per table: every C1/C4 cell for that trigger whose keep edge was above its complement edge on
train (`research/diagnostics/composite_ingredients.md`, read 13 Nov 2026):

    day bearish   E2A   G1 G2 G3 G4 G8 G10       (not G5, G6: keep below complement)
    day bullish   T04   G3 G4 G7 G9 G10          (not G5, G6, G8)
    week bullish  A05B  G1 G4 G5 G6 G9 G10       (not G2, G7, G8)
    week bearish  A01   G1 G2 G3 G7 G8 G10       (not G4, G5, G6)

Families:

A. vote, k of n: a trigger pick is kept if at least k candidate gates return True. A gate with no verdict
   counts as not passed; a pick for which NO candidate gate has a verdict abstains. Survivors keep the
   trigger's own unchanged score.
B. rank boost, w: every trigger pick stays; score = trigger score x (1 + w x passes), passes = number of
   candidate gates returning True. The factor is at least 1, so the sign never changes; only the order the
   engine's `top` selection reads changes.
C. threshold variant: trigger AND one gate at an alternative setting, through the gate's optional keyword
   in `strategies/g_gates.py` (whose default reproduces C1 exactly). G2's cut is stated for the bearish
   side (leader percentile above c); the bullish side mirrors it (below 1 - c).

Every gate is imported from `strategies.g_gates`, never copied. All candidate gates of one table are computed
once per call (one `g_gates.shared_tail()` context, so the universe is adjusted once per date) and every vote
count and boost factor is derived from that one set of verdicts. Picks of families A and C are always a
subset of the trigger's side picks. Nothing here names a price level.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategies import composite_v1 as V1
from strategies import e_confluence_core as core
from strategies import g_gates as G

TABLES: dict[str, str] = {
    "day_bullish": "t04",
    "day_bearish": "e2a",
    "week_bullish": "a05b",
    "week_bearish": "a01",
}
HORIZON_TABLES: dict[str, tuple[str, str]] = {
    "day": ("day_bullish", "day_bearish"),
    "week": ("week_bullish", "week_bearish"),
}

# Read off the C1 table (keep edge > complement edge, train, top selection). Do not edit without a new card.
CANDIDATES: dict[str, tuple[str, ...]] = {
    "day_bearish": ("g1", "g2", "g3", "g4", "g8", "g10"),
    "day_bullish": ("g3", "g4", "g7", "g9", "g10"),
    "week_bullish": ("g1", "g4", "g5", "g6", "g9", "g10"),
    "week_bearish": ("g1", "g2", "g3", "g7", "g8", "g10"),
}

# The C1 numbers the candidate lists were read from: (keep edge, complement edge), points.
C1_KEEP_VS_COMPLEMENT: dict[str, dict[str, tuple[float, float]]] = {
    "day_bearish": {"g1": (8.64, 6.64), "g2": (8.31, 7.15), "g3": (7.71, -0.83), "g4": (6.63, 6.13),
                    "g5": (6.77, 9.51), "g6": (6.32, 7.45), "g8": (7.13, 4.41), "g10": (9.07, 6.73)},
    "day_bullish": {"g3": (3.71, 2.33), "g4": (3.65, 2.24), "g5": (2.36, 3.98), "g6": (2.60, 4.08),
                    "g7": (3.40, -0.05), "g8": (1.42, 4.37), "g9": (5.12, 2.61), "g10": (3.42, 3.32)},
    "week_bullish": {"g1": (2.41, 1.09), "g2": (1.14, 1.59), "g4": (1.64, 1.36), "g5": (3.80, 1.01),
                     "g6": (3.15, 2.30), "g7": (0.36, 0.67), "g8": (1.29, 1.35), "g9": (1.86, 1.54),
                     "g10": (2.90, 2.00)},
    "week_bearish": {"g1": (2.85, 0.19), "g2": (2.78, -0.18), "g3": (2.48, -1.76), "g4": (0.96, 2.39),
                     "g5": (2.42, 2.60), "g6": (-0.15, 2.73), "g7": (3.06, 0.16), "g8": (3.06, 1.41),
                     "g10": (3.22, 1.36)},
}


@dataclass(frozen=True)
class Setting:
    """One horizon-level setting; built on each table of the horizon where it exists."""

    key: str            # e.g. "vote_k3", "boost_w0p5", "g8_x2p0"
    family: str         # "vote" (A), "boost" (B) or "threshold" (C)
    value: float        # k, w, or the gate's alternative threshold
    gate: str | None = None
    param: str | None = None  # the gate's real keyword name (G2: bearish-side name; see gate_kwargs)

    @property
    def family_letter(self) -> str:
        return {"vote": "A", "boost": "B", "threshold": "C"}[self.family]


def _num(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", "p") if x != int(x) else f"{int(x)}p0"


def _vote(k: int) -> Setting:
    return Setting(f"vote_k{k}", "vote", k)


def _boost(w: float) -> Setting:
    return Setting(f"boost_w{_num(w)}", "boost", w)


def _thr(gate: str, tag: str, param: str, value: float) -> Setting:
    return Setting(f"{gate}_{tag}{_num(value)}", "threshold", value, gate, param)


BOOST_WEIGHTS = (0.25, 0.5, 1.0)
# Alternatives either side of today's value (C1 value in brackets).
G2_CUTS = (0.60, 0.80)          # leader percentile cut (0.70); bullish side mirrors to 0.40 / 0.20 (0.30)
G5_QUANTILES = (0.40, 0.60)     # stress level: 20-day vol above this quantile of its 250 values (median)
G8_MULTIPLES = (1.25, 2.0)      # volume surge multiple (1.5)
G9_NEAR_HIGHS = (0.80, 0.90)    # pullback: close at least this share of the 252-day high (0.85)

_THRESHOLDS = (
    [_thr("g2", "cut", "leader_top", c) for c in G2_CUTS]
    + [_thr("g8", "x", "volume_multiple", m) for m in G8_MULTIPLES]
    + [_thr("g5", "q", "stress_quantile", q) for q in G5_QUANTILES]
    + [_thr("g9", "near", "near_high", h) for h in G9_NEAR_HIGHS]
)

# Budget (cards/COMPOSITE_V2.yml): at most 14 configs per day table and 60 week configs. Dropped for budget,
# day only: G3 residual-z variants for E2A (0.5, 1.5; one side only, T04's G3 has no numeric threshold) and
# the E2A 6-of-6 vote (one side only, and the all-gates AND is the shape that over-fitted in V1).
SETTINGS: dict[str, list[Setting]] = {
    "day": [_vote(k) for k in range(1, 6)] + [_boost(w) for w in BOOST_WEIGHTS] + _THRESHOLDS,
    "week": [_vote(k) for k in range(1, 7)] + [_boost(w) for w in BOOST_WEIGHTS] + _THRESHOLDS,
}
DROPPED_FOR_BUDGET = {
    "day": [
        "day_g3_z0p5, day_g3_z1p5: E2A residual-z minimum 0.5 / 1.5 (C1: 1.0), E2A only",
        "day_vote_k6: E2A 6 of 6, E2A only (T04 has 5 candidates)",
    ],
    "week": [],
}
NOT_BUILT = {
    "g3 (T04, A01)": "no numeric threshold: the gate is the sign of the market-adjusted move",
}


def horizon_of(table: str) -> str:
    return G.TRIGGERS[TABLES[table]].horizon


def config_key(table: str, setting: Setting) -> str:
    return f"{horizon_of(table)}_{setting.key}"


def builds(table: str, setting: Setting) -> bool:
    """Whether `setting` exists on `table` (vote k within the candidates, threshold gate a C1 cell)."""
    trigger = TABLES[table]
    if setting.family == "vote":
        n = len(CANDIDATES[table])
        if setting.value > n:
            return False
        if setting.value == n and set(CANDIDATES[table]) == set(V1.COMPOSITES[table][1]):
            return False  # all of n would repeat COMPOSITE_V1
        return True
    if setting.family == "boost":
        return True
    return (trigger, setting.gate) in G.CELLS


CONFIGS: dict[tuple[str, str], Setting] = {
    (table, s.key): s for horizon, settings in SETTINGS.items() for s in settings for table in HORIZON_TABLES[horizon]
    if builds(table, s)
}


def _check() -> None:
    for table, gates in CANDIDATES.items():
        trig = TABLES[table]
        t = G.TRIGGERS[trig]
        if table != f"{t.horizon}_{t.side_word}":
            raise ValueError(f"table {table}: trigger {trig} sits on the {t.horizon} {t.side_word} table")
        for g in gates:
            if (trig, g) not in G.CELLS:
                raise ValueError(f"candidate {trig} x {g} is not a C1 cell")
            keep, comp = C1_KEEP_VS_COMPLEMENT[table][g]
            if not keep > comp:
                raise ValueError(f"candidate {trig} x {g}: keep edge not above complement in C1")
        for g, (keep, comp) in C1_KEEP_VS_COMPLEMENT[table].items():
            if keep > comp and g not in gates:
                raise ValueError(f"{trig} x {g} beat its complement in C1 but is not a candidate")


_check()


def config_id(table: str, setting_key: str) -> str:
    return f"COMPOSITE_V2_{table}_{setting_key}".upper()


def gate_kwargs(table: str, setting: Setting) -> dict[str, float]:
    """The real keyword(s) passed to the gate on this table."""
    if setting.family != "threshold":
        return {}
    if setting.gate == "g2" and G.TRIGGERS[TABLES[table]].side > 0:
        return {"leader_bottom": round(1.0 - setting.value, 10)}
    return {setting.param: setting.value}


def describe(table: str, setting: Setting) -> str:
    t = G.TRIGGERS[TABLES[table]]
    gates = " ".join(g.upper() for g in CANDIDATES[table])
    if setting.family == "vote":
        return f"at least {int(setting.value)} of {len(CANDIDATES[table])} gates ({gates}) hold"
    if setting.family == "boost":
        return f"every pick kept, score x (1 + {setting.value:g} x gates holding among {gates})"
    kw = ", ".join(f"{k}={v:g}" for k, v in gate_kwargs(table, setting).items())
    return f"{setting.gate.upper()} {G.GATE_NAMES[setting.gate].split(' (')[0]} holds at {kw}"


# ---------------------------------------------------------------- verdicts, computed once per call


def candidate_verdicts(table: str, history: pd.DataFrame) -> tuple[pd.Series, dict[str, dict[str, bool]]]:
    """The trigger's side scores and {gate: {symbol: verdict}} for every candidate gate, each gate asked once."""
    trigger = TABLES[table]
    base = G.trigger_side_scores(trigger, history)
    if base.empty:
        return base, {}
    side = G.TRIGGERS[trigger].side
    sides = {s: side for s in base.index}
    with G.shared_tail():
        per_gate = {g: {s: bool(x) for s, x in G.GATES[g](history, sides, trigger).items()} for g in CANDIDATES[table]}
    return base, per_gate


def pass_counts(base: pd.Series, per_gate: dict[str, dict[str, bool]]) -> tuple[dict[str, int], set[str]]:
    """(passes per pick, picks at least one gate judged). No verdict counts as not passed."""
    passes = {s: sum(bool(v.get(s, False)) for v in per_gate.values()) for s in base.index}
    judged = {s for s in base.index if any(s in v for v in per_gate.values())}
    return passes, judged


def vote_from(base: pd.Series, per_gate: dict, k: int) -> pd.Series:
    passes, judged = pass_counts(base, per_gate)
    return core.keep_if(base, {s: passes[s] >= k for s in judged})


def boost_from(base: pd.Series, per_gate: dict, w: float) -> pd.Series:
    passes, _ = pass_counts(base, per_gate)
    if base.empty:
        return base
    factor = pd.Series({s: 1.0 + w * passes[s] for s in base.index}, dtype=float)
    return (base.astype(float) * factor).astype(float)


def all_settings_from(table: str, history: pd.DataFrame) -> dict[str, pd.Series]:
    """Every vote and boost config of `table` from one set of verdicts (tests, audit and diagnostics)."""
    base, per_gate = candidate_verdicts(table, history)
    out = {}
    for (t, key), s in CONFIGS.items():
        if t != table:
            continue
        if s.family == "vote":
            out[key] = vote_from(base, per_gate, int(s.value))
        elif s.family == "boost":
            out[key] = boost_from(base, per_gate, s.value)
    return out


def threshold_verdicts(table: str, setting: Setting, history: pd.DataFrame) -> tuple[pd.Series, dict[str, bool]]:
    trigger = TABLES[table]
    base = G.trigger_side_scores(trigger, history)
    if base.empty:
        return base, {}
    side = G.TRIGGERS[trigger].side
    v = G.GATES[setting.gate](history, {s: side for s in base.index}, trigger, **gate_kwargs(table, setting))
    return base, {s: bool(x) for s, x in v.items()}


def config_score(table: str, setting_key: str, history: pd.DataFrame) -> pd.Series:
    s = CONFIGS[(table, setting_key)]
    if s.family == "threshold":
        base, v = threshold_verdicts(table, s, history)
        return core.keep_if(base, v)
    base, per_gate = candidate_verdicts(table, history)
    if s.family == "vote":
        return vote_from(base, per_gate, int(s.value))
    return boost_from(base, per_gate, s.value)


def config(table: str, setting_key: str):
    """`(score, rules_fired)` for one table's config."""
    if (table, setting_key) not in CONFIGS:
        raise ValueError(f"no COMPOSITE_V2 config {setting_key!r} on table {table!r}")
    s = CONFIGS[(table, setting_key)]
    t, cid = G.TRIGGERS[TABLES[table]], config_id(table, setting_key)
    what = describe(table, s)

    def score(history: pd.DataFrame) -> pd.Series:
        return config_score(table, setting_key, history)

    def fired(history: pd.DataFrame, symbol: str) -> str:
        # Full history, not the symbol's own rows: several gates read the universe.
        if symbol not in config_score(table, setting_key, history).index:
            return f"{cid}: no {t.label} {t.side_word} pick, or the gates gave no verdict or too few passed, abstain"
        if s.family == "boost":
            base, per_gate = candidate_verdicts(table, history)
            passes, _ = pass_counts(base, per_gate)
            held = [g.upper() for g in CANDIDATES[table] if per_gate.get(g, {}).get(symbol)]
            return (f"{cid}: {t.label} {t.side_word} pick, {passes[symbol]} of {len(CANDIDATES[table])} gates hold "
                    f"({' '.join(held) or 'none'}), rank weight x{1.0 + s.value * passes[symbol]:g}. "
                    + t.mod.rules_fired(history, symbol))
        return f"{cid}: {t.label} {t.side_word} pick where {what}. " + t.mod.rules_fired(history, symbol)

    score.__doc__ = f"{cid}: {t.label} {t.side_word} scores, {what}."
    return score, fired
