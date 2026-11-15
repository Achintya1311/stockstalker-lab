# Bullish trials (BULLISH_PLAN B1 to B5): train results

Train split only (2015 to 2020), bullish side, `top` selection (the picks per date the run's basket keeps; `Top n`). Observation only: no number here is a gate, a roster input or shown on the desk. Rebuilt by `python3 -m scripts.bull_report`.

Yardstick `absolute`: a bullish pick is right when the stock rose over the horizon; market line = share of universe stocks that rose (SPEC.md section 3). Yardstick `relative`: right when the stock did better than the median universe stock on that pick date; market line = exact share of universe stocks above that median (at or just under 50%). Costs cancel in the relative comparison; the directional move after costs is the usual absolute one either way.

PASS (plan's bar, fixed 14 Nov 2026): picks >= 500; edge >= 3 points (exit runs: average R above the universe baseline > 0 with t >= 2); positive in >= 4 of 6 train years; directional move after costs > 0. A pass earns exactly one check on the unseen 2021 to 2023 years; it goes forward only if it holds there and beats the current rule for its table by at least 1 point.

Intervals: month rows use the engine's moving-block bootstrap (block t); day and week rows use the engine's per-date t, interval = edge +/- 1.96 x standard error.

| Id | Horizon | Yardstick | Top n | Picks | Dates | Hit rate | Market line | Edge (pts) | t | 95% interval | Years positive | Dir. move after costs | Avg R above baseline (t) | Profit factor | PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b1-trend-cross-trail-day | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b1-trend-cross-trail-week | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b2-a04-relative-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b2-a04-relative-week | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b2-m01-relative-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b2-m01-relative-week | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b2-m02-relative-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b3-m01-top10-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b3-m01-top15-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b3-m01-top20-month | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b4-long-liquidation-end-day | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b4-put-writing-day | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b5-failed-bearish-day | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b5-failed-bearish-week | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

Passing: none yet.

## Live comparison (current bullish rules, edge in points, absolute yardstick, top 5)

| Table | Rule | Train edge | Released validation edge |
|---|---|---|---|
| day bullish | T04 (t04_connors_rsi2) | +3.37 | +4.36 |
| week bullish | A05B (a05b_max_effect_ranked) | +2.23 | +2.23 |

A relative-yardstick edge and an absolute one answer different questions, so they are not directly comparable; a wider basket is not what a five-row table publishes. SPEC.md needs a wording amendment before either is used for a roster decision (`state/engine-issues.md`).
