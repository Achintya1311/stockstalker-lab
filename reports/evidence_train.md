# Evidence, train split: block-bootstrap intervals and data-snooping control

Edge is in points of hit rate over the market line, per pick date, `top` selection, as in `train_leaderboard.md`. The 95% interval and P(edge <= 0) come from a stationary bootstrap over dates (block length chosen per series), so serial correlation is respected. SPA is Hansen's test that NO strategy beats the market line across all trials of that horizon and side (small p = something real survives snooping). StepM names the strategies individually superior at the 10% level. MCS is the set statistically indistinguishable from the best at 10%. Dates with no pick count as edge 0 in the joint tests.

## day/bearish  (34 experiments, block 1)

SPA p-value (consistent): **0.000**  (lower 0.000, upper 0.000). StepM superior: a02-extreme-day-reversal-day, a09-gap-fade-day, consensus-db-v1-day, d01c-day, e1b-day, e2a-d01c-fallback-day, e2a-day, e2b-day, t01-sma-crossover-day, t04-connors-rsi2-day, t05c-upcross-fade-day, t06-bollinger-pctb-day, t13-williams-r-day, t15-adx-regime-day. MCS size: 3 of 34.

| Experiment | Dates | Coverage | Edge (pts) | 95% interval | P(edge<=0) | Block |
|---|---|---|---|---|---|---|
| e2a-day | 936 | 64% | +7.46 | +5.27 to +9.67 | 0.000 | 2 |
| e2a-d01c-fallback-day | 1386 | 94% | +5.97 | +4.37 to +7.57 | 0.000 | 2 |
| d01c-day | 1465 | 100% | +4.74 | +3.71 to +5.84 | 0.000 | 2 |
| consensus-db-v1-day | 1467 | 100% | +4.61 | +3.52 to +5.70 | 0.000 | 1 |
| a02-extreme-day-reversal-day | 1273 | 87% | +4.34 | +2.62 to +6.06 | 0.000 | 2 |
| e1a-day | 248 | 17% | +4.31 | -0.83 to +9.47 | 0.045 | 1 |
| e1b-day | 1264 | 86% | +4.29 | +2.69 to +5.90 | 0.000 | 1 |
| t06-bollinger-pctb-day | 1329 | 91% | +3.35 | +1.85 to +4.80 | 0.000 | 1 |
| a09-gap-fade-day | 1272 | 87% | +3.21 | +1.64 to +4.67 | 0.000 | 1 |
| t13-williams-r-day | 1445 | 99% | +2.89 | +1.76 to +4.04 | 0.000 | 3 |
| t05c-upcross-fade-day | 1300 | 89% | +2.70 | +1.07 to +4.27 | 0.001 | 1 |
| e2b-day | 1074 | 73% | +2.34 | +0.29 to +4.37 | 0.013 | 1 |
| t04-connors-rsi2-day | 1123 | 77% | +2.32 | +0.57 to +3.98 | 0.004 | 1 |
| t15-adx-regime-day | 1404 | 96% | +2.20 | +1.09 to +3.33 | 0.000 | 2 |
| t01-sma-crossover-day | 1436 | 98% | +1.89 | +0.80 to +2.95 | 0.001 | 2 |
| champion-v1-day | 1436 | 98% | +1.37 | +0.26 to +2.50 | 0.009 | 1 |
| a08-overnight-intraday-tug-day | 1465 | 100% | +1.15 | -0.00 to +2.33 | 0.025 | 1 |
| o03-trend-confirmed-day | 1267 | 86% | +0.90 | -0.72 to +2.48 | 0.135 | 1 |
| t03-rsi-thresholds-day | 1259 | 86% | +0.89 | -0.70 to +2.44 | 0.128 | 1 |
| o01-retest-day | 1389 | 95% | +0.66 | -0.78 to +1.97 | 0.180 | 1 |
| o04b-no-d01-day | 1389 | 95% | +0.33 | -1.02 to +1.67 | 0.319 | 1 |
| t09-supertrend-day | 1426 | 97% | +0.32 | -0.80 to +1.46 | 0.292 | 2 |
| o02-oi-confirmed-day | 802 | 55% | +0.01 | -2.38 to +2.36 | 0.486 | 2 |
| t05-macd-crossover-day | 1323 | 90% | -0.06 | -1.56 to +1.44 | 0.522 | 2 |
| t11-inside-bar-day | 1377 | 94% | -0.08 | -1.28 to +1.21 | 0.559 | 2 |
| t10-nr4-narrow-range-day | 1405 | 96% | -0.23 | -1.48 to +1.08 | 0.639 | 2 |
| t12-stochastic-day | 1279 | 87% | -0.31 | -1.83 to +1.27 | 0.644 | 2 |
| o04a-no-volume-day | 1389 | 95% | -0.37 | -1.78 to +1.03 | 0.687 | 1 |
| t10-nr7-narrow-range-day | 1346 | 92% | -0.55 | -1.83 to +0.81 | 0.785 | 2 |
| o00-placebo-day | 1426 | 97% | -0.65 | -1.72 to +0.43 | 0.887 | 1 |
| o04-order-block-composite-day | 1389 | 95% | -0.65 | -2.00 to +0.72 | 0.824 | 1 |
| c01-day-of-week-day | 1380 | 94% | -1.15 | -2.22 to -0.17 | 0.986 | 3 |
| t14-cci-day | 1322 | 90% | -1.29 | -2.67 to +0.17 | 0.956 | 2 |
| d01-oi-buildup-day | 1467 | 100% | -2.48 | -3.54 to -1.44 | 1.000 | 1 |

## day/bullish  (30 experiments, block 1)

SPA p-value (consistent): **0.003**  (lower 0.000, upper 0.004). StepM superior: d01c-day, t04-connors-rsi2-day, t10-nr7-narrow-range-day. MCS size: 7 of 30.

| Experiment | Dates | Coverage | Edge (pts) | 95% interval | P(edge<=0) | Block |
|---|---|---|---|---|---|---|
| t04-connors-rsi2-day | 1087 | 74% | +3.37 | +1.62 to +5.13 | 0.001 | 1 |
| d01c-day | 1467 | 100% | +2.54 | +1.48 to +3.60 | 0.000 | 1 |
| t10-nr7-narrow-range-day | 1347 | 92% | +2.16 | +0.86 to +3.46 | 0.001 | 1 |
| t10-nr4-narrow-range-day | 1398 | 95% | +1.34 | +0.15 to +2.49 | 0.015 | 1 |
| t06-bollinger-pctb-day | 1217 | 83% | +1.04 | -0.73 to +2.90 | 0.124 | 1 |
| e2b-day | 702 | 48% | +0.88 | -1.68 to +3.45 | 0.269 | 1 |
| a09-gap-fade-day | 1076 | 73% | +0.87 | -1.20 to +2.94 | 0.204 | 2 |
| e1a-day | 217 | 15% | +0.59 | -5.41 to +6.28 | 0.426 | 1 |
| o04b-no-d01-day | 1419 | 97% | +0.23 | -0.98 to +1.47 | 0.345 | 1 |
| a08-overnight-intraday-tug-day | 1465 | 100% | +0.04 | -1.02 to +1.15 | 0.455 | 1 |
| t13-williams-r-day | 1453 | 99% | -0.28 | -1.30 to +0.86 | 0.686 | 1 |
| o03-trend-confirmed-day | 1368 | 93% | -0.36 | -1.51 to +0.88 | 0.725 | 3 |
| t11-inside-bar-day | 1380 | 94% | -0.37 | -1.81 to +0.99 | 0.709 | 3 |
| o01-retest-day | 1419 | 97% | -0.47 | -1.67 to +0.71 | 0.797 | 1 |
| t15-adx-regime-day | 1418 | 97% | -0.64 | -1.77 to +0.46 | 0.874 | 4 |
| e1b-day | 1055 | 72% | -0.91 | -3.01 to +1.13 | 0.794 | 2 |
| o00-placebo-day | 1424 | 97% | -0.95 | -2.05 to +0.14 | 0.957 | 1 |
| o04a-no-volume-day | 1419 | 97% | -1.08 | -2.28 to +0.12 | 0.958 | 2 |
| a02-extreme-day-reversal-day | 1067 | 73% | -1.10 | -2.97 to +0.87 | 0.862 | 2 |
| t03-rsi-thresholds-day | 1324 | 90% | -1.13 | -2.64 to +0.30 | 0.940 | 3 |
| o04-order-block-composite-day | 1419 | 97% | -1.16 | -2.38 to +0.01 | 0.974 | 1 |
| t01-sma-crossover-day | 1428 | 97% | -1.46 | -2.62 to -0.33 | 0.994 | 3 |
| champion-v1-day | 1435 | 98% | -1.55 | -2.73 to -0.36 | 0.996 | 3 |
| e2a-day | 808 | 55% | -1.58 | -4.00 to +0.87 | 0.899 | 1 |
| t14-cci-day | 1274 | 87% | -2.44 | -4.10 to -0.78 | 0.998 | 1 |
| t09-supertrend-day | 1426 | 97% | -2.51 | -3.62 to -1.39 | 1.000 | 1 |
| t05-macd-crossover-day | 1300 | 89% | -2.86 | -4.47 to -1.25 | 1.000 | 1 |
| t12-stochastic-day | 1229 | 84% | -4.53 | -6.20 to -2.86 | 1.000 | 1 |
| d01-oi-buildup-day | 1465 | 100% | -4.61 | -5.75 to -3.57 | 1.000 | 2 |
| o02-oi-confirmed-day | 895 | 61% | -5.15 | -7.30 to -2.83 | 1.000 | 1 |

## week/bearish  (31 experiments, block 1)

SPA p-value (consistent): **0.100**  (lower 0.072, upper 0.100). StepM superior: t05c-upcross-fade-week. MCS size: 31 of 31. a05b-max-effect-ranked-week repeats a05-max-effect-week exactly (same picks every date), so the joint tests ran on one copy.

| Experiment | Dates | Coverage | Edge (pts) | 95% interval | P(edge<=0) | Block |
|---|---|---|---|---|---|---|
| t05c-upcross-fade-week | 276 | 89% | +4.02 | +0.79 to +7.18 | 0.007 | 1 |
| d02-stock-pcr-contrarian-week | 225 | 73% | +3.75 | -0.64 to +8.36 | 0.050 | 1 |
| t01-sma-crossover-week | 303 | 98% | +3.20 | +0.96 to +5.53 | 0.003 | 2 |
| t15-adx-regime-week | 299 | 97% | +2.95 | +0.30 to +5.62 | 0.012 | 1 |
| a01-weekly-reversal-week | 309 | 100% | +2.48 | -0.09 to +5.31 | 0.031 | 1 |
| consensus-wb-v1-week | 309 | 100% | +2.48 | +0.17 to +4.84 | 0.018 | 1 |
| t02-golden-death-cross-week | 271 | 88% | +2.05 | -0.60 to +4.71 | 0.065 | 1 |
| t05-macd-crossover-week | 275 | 89% | +2.02 | -1.36 to +5.31 | 0.113 | 1 |
| t03-rsi-thresholds-week | 268 | 87% | +1.72 | -1.64 to +5.19 | 0.147 | 2 |
| i02-low-vol-level-week | 260 | 84% | +1.58 | -0.88 to +4.06 | 0.115 | 1 |
| a07c-volume-fade-week | 302 | 98% | +1.34 | -1.32 to +3.80 | 0.151 | 1 |
| a03-momentum-12-1-week | 255 | 83% | +0.85 | -1.79 to +3.60 | 0.285 | 1 |
| champion-v1-week | 303 | 98% | +0.41 | -1.91 to +2.70 | 0.359 | 2 |
| o05-order-block-weekly-week | 241 | 78% | +0.32 | -2.46 to +3.28 | 0.417 | 1 |
| o01-retest-week | 293 | 95% | +0.18 | -2.75 to +2.91 | 0.455 | 2 |
| a06-low-volatility-week | 296 | 96% | +0.15 | -2.27 to +2.60 | 0.446 | 2 |
| d02-stock-pcr-confirmatory-week | 302 | 98% | +0.04 | -2.62 to +2.66 | 0.488 | 2 |
| o04a-no-volume-week | 293 | 95% | -0.03 | -2.85 to +2.69 | 0.496 | 2 |
| t09-supertrend-week | 301 | 97% | -0.11 | -2.56 to +2.47 | 0.532 | 1 |
| a05-max-effect-week | 295 | 95% | -0.28 | -2.73 to +2.12 | 0.572 | 1 |
| a05b-max-effect-ranked-week | 295 | 95% | -0.28 | -2.73 to +2.12 | 0.572 | 1 |
| o04-order-block-composite-week | 293 | 95% | -0.44 | -3.28 to +2.22 | 0.619 | 2 |
| a04-52-week-high-week | 260 | 84% | -0.50 | -3.17 to +2.23 | 0.626 | 2 |
| a07-high-volume-premium-week | 302 | 98% | -0.84 | -3.04 to +1.42 | 0.776 | 1 |
| t08-donchian-breakout-55-week | 255 | 83% | -0.90 | -5.08 to +3.38 | 0.662 | 2 |
| o03-trend-confirmed-week | 265 | 86% | -0.91 | -4.25 to +2.58 | 0.695 | 2 |
| o04b-no-d01-week | 293 | 95% | -1.12 | -4.08 to +1.62 | 0.778 | 2 |
| o00-placebo-week | 301 | 97% | -1.48 | -4.07 to +1.04 | 0.875 | 3 |
| t14-cci-week | 282 | 91% | -1.61 | -5.28 to +1.74 | 0.810 | 1 |
| t08-donchian-breakout-20-week | 289 | 94% | -2.72 | -5.86 to +0.34 | 0.966 | 2 |
| c02-turn-of-month-week | 177 | 57% | -2.72 | -5.80 to +0.23 | 0.964 | 1 |

## week/bullish  (27 experiments, block 1)

SPA p-value (consistent): **0.565**  (lower 0.349, upper 0.658). StepM superior: none. MCS size: 26 of 27.

| Experiment | Dates | Coverage | Edge (pts) | 95% interval | P(edge<=0) | Block |
|---|---|---|---|---|---|---|
| a05b-max-effect-ranked-week | 295 | 95% | +2.23 | -0.10 to +4.70 | 0.032 | 1 |
| a04-52-week-high-week | 260 | 84% | +1.92 | -0.89 to +4.59 | 0.088 | 2 |
| o05-order-block-weekly-week | 254 | 82% | +1.90 | -0.61 to +4.37 | 0.069 | 1 |
| i02-low-vol-level-week | 260 | 84% | +1.85 | -1.22 to +5.14 | 0.128 | 2 |
| a06-low-volatility-week | 296 | 96% | +1.55 | -1.00 to +4.01 | 0.117 | 2 |
| t02-golden-death-cross-week | 271 | 88% | +1.09 | -1.82 to +3.79 | 0.231 | 1 |
| a07c-volume-fade-week | 302 | 98% | +0.90 | -1.35 to +3.08 | 0.206 | 1 |
| a03-momentum-12-1-week | 255 | 83% | +0.21 | -2.60 to +2.84 | 0.457 | 1 |
| a01-weekly-reversal-week | 309 | 100% | -0.03 | -2.23 to +2.03 | 0.509 | 2 |
| t03-rsi-thresholds-week | 279 | 90% | -0.33 | -3.67 to +2.75 | 0.592 | 1 |
| d02-stock-pcr-contrarian-week | 302 | 98% | -0.38 | -3.17 to +2.33 | 0.597 | 2 |
| o00-placebo-week | 301 | 97% | -0.61 | -2.74 to +1.62 | 0.705 | 1 |
| t14-cci-week | 267 | 86% | -0.63 | -4.16 to +3.01 | 0.639 | 1 |
| t15-adx-regime-week | 298 | 96% | -1.15 | -3.51 to +1.10 | 0.840 | 3 |
| a07-high-volume-premium-week | 302 | 98% | -1.42 | -3.86 to +1.25 | 0.854 | 1 |
| o03-trend-confirmed-week | 290 | 94% | -1.45 | -3.97 to +1.10 | 0.866 | 1 |
| o04b-no-d01-week | 299 | 97% | -1.68 | -3.94 to +0.51 | 0.934 | 2 |
| t01-sma-crossover-week | 301 | 97% | -1.81 | -3.93 to +0.34 | 0.951 | 3 |
| o01-retest-week | 299 | 97% | -2.21 | -4.47 to -0.12 | 0.981 | 2 |
| champion-v1-week | 303 | 98% | -2.82 | -5.51 to -0.36 | 0.991 | 3 |
| o04a-no-volume-week | 299 | 97% | -2.88 | -5.22 to -0.59 | 0.996 | 1 |
| o04-order-block-composite-week | 299 | 97% | -2.95 | -5.34 to -0.56 | 0.994 | 1 |
| t09-supertrend-week | 301 | 97% | -3.18 | -5.85 to -0.53 | 0.991 | 1 |
| t05-macd-crossover-week | 276 | 89% | -3.90 | -7.04 to -0.68 | 0.991 | 1 |
| t08-donchian-breakout-20-week | 299 | 97% | -3.97 | -6.88 to -0.88 | 0.996 | 1 |
| d02-stock-pcr-confirmatory-week | 225 | 73% | -3.99 | -8.58 to +0.44 | 0.958 | 1 |
| t08-donchian-breakout-55-week | 272 | 88% | -5.09 | -8.38 to -1.76 | 0.997 | 1 |

