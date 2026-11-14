"""Exit-plan payoff table across the exit replays: `research/diagnostics/exit_v1.md`.

    python3 -m scripts.exit_report
    python3 -m scripts.exit_report --done experiments/done --out research/diagnostics/exit_v1.md

Reads every train `experiments/done/*/results.json` that carries an `exit` block (`engine/exits.py`) and
writes one table: rows = rule x exit preset (the side the rule's table uses, `top` selection), columns =
the payoff metrics, with the plain time-only control (same hold, same R unit) next to each row so the
reader sees what the exit plan added. The held replays in `experiments/held/exit/` that have no result yet
are listed as waiting. Train only, observation only: no payoff figure is a gate or a roster input until
SPEC.md has payoff wording (`state/engine-issues.md`). Exit plans are described as parameters in ATR
multiples and R, never as price levels for any stock.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from engine.exits import COST_NOTE

DONE = Path("experiments/done")
HELD = Path("experiments/held/exit")
PENDING = Path("experiments/pending")
OUT = Path("research/diagnostics/exit_v1.md")
COLUMNS = ["Rule", "Horizon", "Side", "Exit plan", "Picks", "Right", "Avg R", "Median R", "Profit factor",
           "Avg %", "Avg hold", "Stop / target / time", "Worst losing run", "Avg R above baseline (t, 95% interval)",
           "Control avg R", "Control above baseline (t)", "Exit minus control (avg R)"]


def _f(x, digits=3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def _p(x, digits=1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def _rule(exp_id: str) -> str:
    # exit-<rule>-<preset>-<horizon>
    parts = exp_id.split("-")
    return parts[1].upper() if len(parts) >= 4 and parts[0] == "exit" else exp_id


def rows(done_dir: Path) -> list[list[str]]:
    out = []
    for f in sorted(done_dir.glob("*/results.json")):
        r = json.loads(f.read_text())
        block = r.get("exit")
        if block is None or r.get("split") != "train":
            continue
        for side, m in block["sides"].items():
            if not m.get("n_picks"):
                out.append([_rule(r["id"]), r["horizon"], side, block["plan_label"], "0"] + [""] * (len(COLUMNS) - 5))
                continue
            c = m.get("control") or (m if block["plan"]["kind"] == "time" else None)
            iv = m.get("interval")
            above = (f"{_f(m['avg_r_above_baseline'])} (t {_f(m['t'], 2)}, "
                     f"{'n/a' if iv is None else f'{iv[0]:.3f} to {iv[1]:.3f}'})")
            ctrl_avg = _f(c["avg_r"]) if c else "n/a"
            ctrl_above = f"{_f(c['avg_r_above_baseline'])} (t {_f(c['t'], 2)})" if c else "n/a"
            gain = _f(m["avg_r"] - c["avg_r"]) if c else "n/a"
            out.append([
                _rule(r["id"]), r["horizon"], side, block["plan_label"], str(m["n_picks"]), _p(m["share_right"]),
                _f(m["avg_r"]), _f(m["median_r"]), _f(m["profit_factor"], 2), _p(m["avg_pct"], 2),
                _f(m["avg_holding_sessions"], 1),
                f"{_p(m['share_stop'], 0)} / {_p(m['share_target'], 0)} / {_p(m['share_time'], 0)}",
                str(m["worst_losing_run"]), above, ctrl_avg, ctrl_above, gain,
            ])
    return out


def waiting(done_dir: Path, held_dir: Path, pending_dir: Path) -> list[str]:
    ids = sorted({yaml.safe_load(p.read_text())["id"] for p in held_dir.rglob("*.yml")}
                 | {yaml.safe_load(p.read_text())["id"] for p in pending_dir.glob("exit-*.yml")})
    return [i for i in ids if not (done_dir / i / "results.json").exists()]


def render(done_dir: Path = DONE, held_dir: Path = HELD, pending_dir: Path = PENDING) -> str:
    body = rows(done_dir)
    lines = [
        "# Exit plans v1: payoff by rule and exit plan (train only)", "",
        "Train split (2015 to 2020), the `top` picks of the side each rule's table uses. Hit rate says how often a "
        "pick's direction was right; this table says what the picks paid under an exit plan. Entry convention: "
        "the pick date's open (the engine's usual one). Risk unit R = stop_atr x ATR(14) known before the pick "
        f"date. Outcomes are net of the {COST_NOTE}. Exit plans are given as parameters in ATR multiples and R only.",
        "",
        "- **fixed**: stop 1R (2 ATR), target 2R, time exit after 10 sessions; a session touching both counts "
        "as a stop; a gap fills at the open.",
        "- **trail**: stop 3 ATR from the best close since entry (1R = 3 ATR), time exit after 20 sessions.",
        "- **time**: exit at the close of session 10, no stop (1R = 2 ATR): the plain time-only control.",
        "", "Each row's control is the time-only plan with the same hold and the same R unit, computed on the same "
        "picks, so *exit minus control* is what the exit plan added. *Avg R above baseline* = per date, the picks' "
        "average R minus the average R of every universe stock under the same plan, averaged over dates; t and "
        "interval use blocks of consecutive pick dates because holds overlap (method in each results.md).", "",
        "Observation only. No payoff figure is a gate, a roster input or desk content until SPEC.md is amended "
        "(`state/engine-issues.md`).", "",
    ]
    if body:
        lines += ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
        lines += ["| " + " | ".join(r) + " |" for r in body]
    else:
        lines += ["No exit replay has a result yet."]
    wait = waiting(done_dir, held_dir, pending_dir)
    if wait:
        lines += ["", f"Waiting for a replay ({len(wait)}): " + ", ".join(f"`{w}`" for w in wait) + "."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--done", default=str(DONE))
    ap.add_argument("--held", default=str(HELD))
    ap.add_argument("--pending", default=str(PENDING))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(Path(a.done), Path(a.held), Path(a.pending)))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
