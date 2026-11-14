# Exit plans v1: payoff by rule and exit plan (train only)

Train split (2015 to 2020), the `top` picks of the side each rule's table uses. Hit rate says how often a pick's direction was right; this table says what the picks paid under an exit plan. Entry convention: the pick date's open (the engine's usual one). Risk unit R = stop_atr x ATR(14) known before the pick date. Outcomes are net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Exit plans are given as parameters in ATR multiples and R only.

- **fixed**: stop 1R (2 ATR), target 2R, time exit after 10 sessions; a session touching both counts as a stop; a gap fills at the open.
- **trail**: stop 3 ATR from the best close since entry (1R = 3 ATR), time exit after 20 sessions.
- **time**: exit at the close of session 10, no stop (1R = 2 ATR): the plain time-only control.

Each row's control is the time-only plan with the same hold and the same R unit, computed on the same picks, so *exit minus control* is what the exit plan added. *Avg R above baseline* = per date, the picks' average R minus the average R of every universe stock under the same plan, averaged over dates; t and interval use blocks of consecutive pick dates because holds overlap (method in each results.md).

Observation only. No payoff figure is a gate, a roster input or desk content until SPEC.md is amended (`state/engine-issues.md`).

No exit replay has a result yet.

Waiting for a replay (12): `exit-a01-fixed-week`, `exit-a01-time-week`, `exit-a01-trail-week`, `exit-a05b-fixed-week`, `exit-a05b-time-week`, `exit-a05b-trail-week`, `exit-e2a-fixed-day`, `exit-e2a-time-day`, `exit-e2a-trail-day`, `exit-t04-fixed-day`, `exit-t04-time-day`, `exit-t04-trail-day`.
