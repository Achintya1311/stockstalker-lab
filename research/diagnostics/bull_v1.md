# Bullish trials (BULLISH_PLAN B1 to B5): train results

Train split only (2015 to 2020), bullish side, `top` selection (the picks per date the run's basket keeps; `Top n`). Observation only: no number here is a gate, a roster input or shown on the desk. Rebuilt by `python3 -m scripts.bull_report`.

Yardstick `absolute`: a bullish pick is right when the stock rose over the horizon; market line = share of universe stocks that rose (SPEC.md section 3). Yardstick `relative`: right when the stock did better than the median universe stock on that pick date; market line = exact share of universe stocks above that median (at or just under 50%). Costs cancel in the relative comparison; the directional move after costs is the usual absolute one either way.

PASS (plan's bar, fixed 14 Nov 2026): picks >= 500; edge >= 3 points (exit runs: average R above the universe baseline > 0 with t >= 2); positive in >= 4 of 6 train years; directional move after costs > 0. A pass earns exactly one check on the unseen 2021 to 2023 years; it goes forward only if it holds there and beats the current rule for its table by at least 1 point.

Intervals: month rows use the engine's moving-block bootstrap (block t); day and week rows use the engine's per-date t, interval = edge +/- 1.96 x standard error.

| Id | Horizon | Yardstick | Top n | Picks | Dates | Hit rate | Market line | Edge (pts) | t | 95% interval | Years positive | Dir. move after costs | Avg R above baseline (t) | Profit factor | PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b1-trend-cross-trail-day | day | absolute | 5 | 887 | 550 | 44.0% | 44.5% | -0.57 | -0.32 | -4.06 to +2.93 | 5 / 6 (payoff); 3 / 6 (edge) | -0.13% (exit plan); -0.52% (horizon) | 0.035 (t 1.14) | 0.98 | no |
| b1-trend-cross-trail-week | week | absolute | 5 | 194 | 123 | 47.4% | 49.6% | -2.24 | -0.59 | -9.73 to +5.25 | 4 / 6 (payoff); 2 / 6 (edge) | 0.27% (exit plan); -0.05% (horizon) | 0.160 (t 2.21) | 1.14 | no |
| b2-a04-relative-month | month | relative | 5 | 1280 | 256 | 51.4% | 49.8% | +1.58 | 0.63 | -3.11 to +5.74 | 3 / 5 | -0.37% |  |  | no |
| b2-a04-relative-week | week | relative | 5 | 1300 | 260 | 51.6% | 49.8% | +1.79 | 1.10 | -1.39 to +4.97 | 4 / 5 | -0.55% |  |  | no |
| b2-m01-relative-month | month | relative | 5 | 1255 | 251 | 50.8% | 49.8% | +0.93 | 0.48 | -3.14 to +5.30 | 3 / 5 | 0.03% |  |  | no |
| b2-m01-relative-week | week | relative | 5 | 1275 | 255 | 50.4% | 49.8% | +0.53 | 0.34 | -2.47 to +3.53 | 3 / 5 | -0.57% |  |  | no |
| b2-m02-relative-month | month | relative | 5 | 1222 | 255 | 50.5% | 49.8% | +1.42 | 0.97 | -2.08 to +4.31 | 3 / 5 | -0.49% |  |  | no |
| b3-m01-top10-month | month | absolute | 10 | 2510 | 251 | 54.5% | 53.6% | +0.98 | 0.67 | -2.06 to +4.06 | 2 / 5 | -0.05% |  |  | no |
| b3-m01-top15-month | month | absolute | 15 | 3765 | 251 | 54.7% | 53.6% | +1.13 | 0.91 | -1.35 to +3.65 | 2 / 5 | -0.04% |  |  | no |
| b3-m01-top20-month | month | absolute | 20 | 5020 | 251 | 55.2% | 53.6% | +1.62 | 1.57 | -0.35 to +3.86 | 2 / 5 | -0.00% |  |  | no |
| b4-long-liquidation-end-day | not run yet |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| b4-put-writing-day | day | absolute | 5 | 6820 | 1386 | 43.8% | 44.9% | -1.27 | -2.12 | -2.44 to -0.10 | 2 / 6 | -0.55% |  |  | no |
| b5-failed-bearish-day | day | absolute | 5 | 1633 | 692 | 44.0% | 43.6% | +1.30 | 0.91 | -1.49 to +4.09 | 5 / 6 | -0.54% |  |  | no |
| b5-failed-bearish-week | week | absolute | 5 | 305 | 137 | 51.8% | 47.0% | +7.05 | 2.26 | +0.95 to +13.15 | 6 / 6 | -0.68% |  |  | no |

Passing: none yet.

## Live comparison (current bullish rules, edge in points, absolute yardstick, top 5)

| Table | Rule | Train edge | Released validation edge |
|---|---|---|---|
| day bullish | T04 (t04_connors_rsi2) | +3.37 | +4.36 |
| week bullish | A05B (a05b_max_effect_ranked) | +2.23 | +2.23 |

A relative-yardstick edge and an absolute one answer different questions, so they are not directly comparable; a wider basket is not what a five-row table publishes. SPEC.md needs a wording amendment before either is used for a roster decision (`state/engine-issues.md`).
