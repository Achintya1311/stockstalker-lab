# Exit plans v1: payoff by rule and exit plan (train only)

Train split (2015 to 2020), the `top` picks of the side each rule's table uses. Hit rate says how often a pick's direction was right; this table says what the picks paid under an exit plan. Entry convention: the pick date's open (the engine's usual one). Risk unit R = stop_atr x ATR(14) known before the pick date. Outcomes are net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Exit plans are given as parameters in ATR multiples and R only.

- **fixed**: stop 1R (2 ATR), target 2R, time exit after 10 sessions; a session touching both counts as a stop; a gap fills at the open.
- **trail**: stop 3 ATR from the best close since entry (1R = 3 ATR), time exit after 20 sessions.
- **time**: exit at the close of session 10, no stop (1R = 2 ATR): the plain time-only control.

Each row's control is the time-only plan with the same hold and the same R unit, computed on the same picks, so *exit minus control* is what the exit plan added. *Avg R above baseline* = per date, the picks' average R minus the average R of every universe stock under the same plan, averaged over dates; t and interval use blocks of consecutive pick dates because holds overlap (method in each results.md).

Observation only. No payoff figure is a gate, a roster input or desk content until SPEC.md is amended (`state/engine-issues.md`).

| Rule | Horizon | Side | Exit plan | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop / target / time | Worst losing run | Avg R above baseline (t, 95% interval) | Control avg R | Control above baseline (t) | Exit minus control (avg R) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A01 | week | bearish | fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions | 1528 | 47.3% | -0.004 | -0.080 | 0.99 | 0.00% | 8.2 | 30% / 7% / 63% | 16 | 0.019 (t 0.53, -0.044 to 0.076) | 0.019 | 0.050 (t 1.38) | -0.024 |
| A01 | week | bearish | time: exit at the close of session 10 (1R = 2 ATR, no stop) | 1528 | 50.6% | 0.019 | 0.012 | 1.05 | 0.03% | 10.0 | 0% / 0% / 100% | 16 | 0.050 (t 1.38, -0.020 to 0.110) | 0.019 | 0.050 (t 1.38) | 0.000 |
| A01 | week | bearish | trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions | 1518 | 45.0% | 0.005 | -0.141 | 1.01 | 0.23% | 15.8 | 45% / 0% / 55% | 22 | 0.032 (t 1.13, -0.027 to 0.082) | 0.016 | 0.038 (t 1.23) | -0.012 |
| A05B | week | bullish | fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions | 1465 | 45.7% | -0.060 | -0.108 | 0.86 | -0.32% | 8.4 | 28% / 7% / 65% | 26 | 0.023 (t 0.67, -0.032 to 0.078) | -0.066 | 0.016 (t 0.44) | 0.006 |
| A05B | week | bullish | time: exit at the close of session 10 (1R = 2 ATR, no stop) | 1465 | 48.7% | -0.066 | -0.026 | 0.85 | -0.39% | 10.0 | 0% / 0% / 100% | 22 | 0.016 (t 0.44, -0.049 to 0.092) | -0.066 | 0.016 (t 0.44) | 0.000 |
| A05B | week | bullish | trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions | 1455 | 45.6% | -0.008 | -0.099 | 0.98 | 0.06% | 16.4 | 40% / 0% / 60% | 26 | 0.032 (t 0.98, -0.016 to 0.093) | -0.027 | 0.022 (t 0.55) | 0.020 |
| E2A | day | bearish | fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions | 2751 | 48.1% | 0.061 | -0.048 | 1.15 | 0.36% | 8.1 | 30% / 9% / 61% | 19 | 0.094 (t 3.34, 0.037 to 0.150) | 0.049 | 0.064 (t 2.01) | 0.011 |
| E2A | day | bearish | time: exit at the close of session 10 (1R = 2 ATR, no stop) | 2751 | 50.9% | 0.049 | 0.017 | 1.11 | 0.23% | 10.0 | 0% / 0% / 100% | 17 | 0.064 (t 2.01, 0.005 to 0.133) | 0.049 | 0.064 (t 2.01) | 0.000 |
| E2A | day | bearish | trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions | 2709 | 43.6% | 0.017 | -0.182 | 1.04 | 0.07% | 15.5 | 48% / 0% / 52% | 35 | 0.037 (t 1.65, -0.007 to 0.082) | 0.037 | 0.051 (t 1.80) | -0.020 |
| T04 | day | bullish | fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions | 3927 | 44.7% | -0.093 | -0.139 | 0.79 | -0.64% | 8.3 | 31% / 7% / 63% | 88 | 0.013 (t 0.63, -0.035 to 0.064) | -0.110 | -0.004 (t -0.04) | 0.017 |
| T04 | day | bullish | time: exit at the close of session 10 (1R = 2 ATR, no stop) | 3927 | 47.1% | -0.110 | -0.069 | 0.77 | -0.75% | 10.0 | 0% / 0% / 100% | 75 | -0.004 (t -0.04, -0.063 to 0.056) | -0.110 | -0.004 (t -0.04) | 0.000 |
| T04 | day | bullish | trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions | 3897 | 45.0% | -0.041 | -0.113 | 0.90 | -0.37% | 16.0 | 44% / 0% / 56% | 81 | -0.002 (t -0.09, -0.061 to 0.056) | -0.072 | -0.015 (t -0.45) | 0.031 |
