# Train leaderboard (top picks per table)

Train split only (2015 to 2020), the picks a table would publish, ranked by t (how hard the result is to explain by luck). A **candidate** for the provisional rule (SPEC.md section 10) has at least 500 picks, positive edge and positive directional move after costs; it still needs a validation query. Rebuilt by `engine/run_queue.py` on every replay.

Trials recorded: 198. Gate 2's bar at that count: t >= 4.35.

| Experiment | Horizon | Side | Picks | Accuracy | Market line | Edge | t | Clears bar | Dir. move | Positive years | |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d01c-day | day | bearish | 7304 | 59.30% | 54.56% | 4.74 | 8.41 | yes | 0.08 | 100.00% | candidate |
| consensus-db-v1-day | day | bearish | 7335 | 59.14% | 54.54% | 4.61 | 8.32 | yes | 0.07 | 100.00% | candidate |
| e2a-d01c-fallback-day | day | bearish | 4996 | 58.97% | 54.43% | 5.97 | 7.44 | yes | 0.06 | 100.00% | candidate |
| e2a-day | day | bearish | 2767 | 61.44% | 55.08% | 7.46 | 6.92 | yes | 0.13 | 100.00% | candidate |
| f03-conditional-reversal-day | day | bearish | 7332 | 58.07% | 54.54% | 3.54 | 6.36 | yes | -0.05 | 100.00% |  |
| f06-trend-acceleration-day | day | bearish | 7292 | 57.97% | 54.54% | 3.35 | 5.96 | yes | -0.01 | 100.00% |  |
| f02-volume-signed-reversal-day | day | bearish | 7335 | 57.79% | 54.54% | 3.26 | 5.86 | yes | 0.03 | 100.00% | candidate |
| a02-extreme-day-reversal-day | day | bearish | 4641 | 58.54% | 54.48% | 4.34 | 5.24 | yes | -0.04 | 100.00% |  |
| e1b-day | day | bearish | 4547 | 58.52% | 54.55% | 4.29 | 5.13 | yes | -0.04 | 100.00% |  |
| t04-q06-fallback-day | day | bullish | 5621 | 48.87% | 44.94% | 3.85 | 5.12 | yes | -0.42 | 100.00% |  |
| q06r-wide-bar-wick-day | day | bearish | 7305 | 57.33% | 54.53% | 2.79 | 4.98 | yes | 0.01 | 100.00% | candidate |
| d01c-day | day | bullish | 7334 | 47.49% | 44.96% | 2.54 | 4.71 | yes | -0.51 | 83.33% |  |
| t13-williams-r-day | day | bearish | 6967 | 57.90% | 54.70% | 2.89 | 4.71 | yes | -0.02 | 100.00% |  |
| q07-trend-residual-day | day | bearish | 7317 | 57.24% | 54.55% | 2.66 | 4.61 | yes | -0.02 | 100.00% |  |
| q06-wick-balance-day | day | bullish | 7335 | 47.54% | 44.96% | 2.58 | 4.61 | yes | -0.42 | 100.00% |  |
| f07-high-push-fade-day | day | bearish | 7235 | 57.29% | 54.59% | 2.69 | 4.57 | yes | 0.00 | 100.00% | candidate |
| t06-bollinger-pctb-day | day | bearish | 5509 | 58.07% | 54.94% | 3.35 | 4.39 | yes | -0.03 | 100.00% |  |
| a09-gap-fade-day | day | bearish | 4710 | 57.47% | 54.52% | 3.21 | 4.01 |  | 0.03 | 66.67% | candidate |
| t15-adx-regime-day | day | bearish | 6880 | 56.63% | 54.50% | 2.20 | 3.75 |  | -0.06 | 100.00% |  |
| t04-connors-rsi2-day | day | bullish | 3952 | 48.61% | 45.17% | 3.37 | 3.69 |  | -0.41 | 100.00% |  |
| t05c-upcross-fade-day | day | bearish | 4819 | 57.19% | 54.95% | 2.70 | 3.39 |  | -0.06 | 83.33% |  |
| q06r-wide-bar-wick-day | day | bullish | 7300 | 46.84% | 44.96% | 1.88 | 3.32 |  | -0.48 | 100.00% |  |
| t01-sma-crossover-day | day | bearish | 7178 | 56.37% | 54.48% | 1.89 | 3.30 |  | -0.06 | 100.00% |  |
| t10-nr7-narrow-range-day | day | bullish | 5996 | 46.33% | 44.71% | 2.16 | 3.20 |  | -0.49 | 100.00% |  |
| q06-wick-balance-day | day | bearish | 7334 | 56.20% | 54.54% | 1.67 | 2.98 |  | -0.05 | 83.33% |  |
| a01-i01-filter-week | week | bearish | 1274 | 55.34% | 50.76% | 4.17 | 2.89 |  | 0.15 | 100.00% | candidate |
| q01c-thin-volume-fall-week | week | bearish | 1524 | 54.33% | 50.91% | 3.26 | 2.81 |  | 0.12 | 100.00% | candidate |
| t04-connors-rsi2-day | day | bearish | 4264 | 57.55% | 54.82% | 2.32 | 2.65 |  | -0.01 | 83.33% |  |
| f06-trend-acceleration-week | week | bearish | 1543 | 54.05% | 50.91% | 3.15 | 2.64 |  | 0.04 | 83.33% | candidate |
| t01-sma-crossover-week | week | bearish | 1514 | 54.10% | 50.88% | 3.20 | 2.56 |  | -0.03 | 83.33% |  |
| t05c-upcross-fade-week | week | bearish | 1028 | 53.31% | 50.72% | 4.02 | 2.45 |  | 0.24 | 83.33% | candidate |
| champion-v1-day | day | bearish | 7171 | 55.84% | 54.48% | 1.37 | 2.37 |  | -0.05 | 100.00% |  |
| t25-heikin-ashi-day | day | bullish | 5113 | 46.06% | 44.64% | 1.85 | 2.32 |  | -0.50 | 83.33% |  |
| f04-open-volume-corr-day | day | bearish | 7335 | 55.79% | 54.54% | 1.25 | 2.28 |  | -0.03 | 83.33% |  |
| e2b-day | day | bearish | 3143 | 56.12% | 54.36% | 2.34 | 2.25 |  | -0.17 | 83.33% |  |
| t15-adx-regime-week | week | bearish | 1456 | 53.71% | 50.87% | 2.95 | 2.20 |  | 0.02 | 83.33% | candidate |
| t10-nr4-narrow-range-day | day | bullish | 6633 | 46.01% | 44.79% | 1.34 | 2.19 |  | -0.50 | 83.33% |  |
| consensus-wb-v1-week | week | bearish | 1545 | 53.40% | 50.91% | 2.48 | 2.06 |  | 0.15 | 66.67% | candidate |
| a08-overnight-intraday-tug-day | day | bearish | 7325 | 55.69% | 54.53% | 1.15 | 1.97 |  | -0.04 | 100.00% |  |
| a05b-max-effect-ranked-week | week | bullish | 1475 | 51.39% | 49.16% | 2.23 | 1.86 |  | -0.50 | 83.33% |  |
| a01-weekly-reversal-week | week | bearish | 1538 | 53.19% | 50.91% | 2.48 | 1.83 |  | 0.02 | 83.33% | candidate |
| g05-residual-reversal-week | week | bearish | 1495 | 53.38% | 50.98% | 2.40 | 1.79 |  | 0.11 | 66.67% | candidate |
| e1a-day | day | bearish | 406 | 56.90% | 52.80% | 4.31 | 1.68 |  | -0.10 | 83.33% | too few picks |
| d02-stock-pcr-contrarian-week | week | bearish | 661 | 54.31% | 50.91% | 3.75 | 1.68 |  | 0.16 | 66.67% | candidate |
| q05-trend-smoothness-week | week | bearish | 1543 | 52.95% | 50.91% | 2.01 | 1.64 |  | -0.13 | 83.33% |  |
| q07-trend-residual-week | week | bearish | 1544 | 53.04% | 50.91% | 2.16 | 1.64 |  | -0.09 | 100.00% |  |
| q02-return-volume-corr-week | week | bearish | 1545 | 52.69% | 50.91% | 1.77 | 1.62 |  | -0.14 | 83.33% |  |
| t25-heikin-ashi-week | week | bullish | 1102 | 50.45% | 48.37% | 2.74 | 1.59 |  | -0.34 | 50.00% |  |
| q04-range-extreme-timing-week | week | bearish | 1505 | 52.62% | 50.76% | 1.87 | 1.55 |  | -0.20 | 83.33% |  |
| q07-trend-residual-day | day | bullish | 7324 | 45.78% | 44.95% | 0.87 | 1.52 |  | -0.56 | 50.00% |  |
| q03-up-day-balance-week | week | bearish | 1545 | 52.88% | 50.91% | 1.97 | 1.51 |  | -0.09 | 66.67% |  |
| t02-golden-death-cross-week | week | bearish | 1355 | 52.99% | 50.93% | 2.05 | 1.50 |  | -0.21 | 66.67% |  |
| o05-order-block-weekly-week | week | bullish | 1210 | 50.99% | 49.12% | 1.90 | 1.47 |  | -0.39 | 80.00% |  |
| t19-obv-divergence-week | week | bearish | 1407 | 53.23% | 50.91% | 1.79 | 1.39 |  | -0.13 | 83.33% |  |
| c02-turn-of-month-week | week | bullish | 40 | 62.50% | 50.63% | 11.87 | 1.38 |  | 0.77 | 100.00% | too few picks |
| i01-momentum-score-week | week | bearish | 1300 | 53.00% | 50.96% | 2.04 | 1.37 |  | -0.17 | 100.00% |  |
| a04-52-week-high-week | week | bullish | 1300 | 50.77% | 48.85% | 1.92 | 1.28 |  | -0.55 | 80.00% |  |
| a06-low-volatility-week | week | bullish | 1458 | 50.55% | 49.10% | 1.55 | 1.24 |  | -0.50 | 66.67% |  |
| i02-low-vol-level-week | week | bearish | 1300 | 52.54% | 50.96% | 1.58 | 1.20 |  | -0.02 | 80.00% |  |
| q03-up-day-balance-day | day | bearish | 7325 | 55.19% | 54.53% | 0.66 | 1.19 |  | -0.12 | 83.33% |  |
| t05-macd-crossover-week | week | bearish | 1008 | 53.27% | 51.11% | 2.02 | 1.19 |  | 0.22 | 66.67% | candidate |
| t20-volume-breakout-day | day | bearish | 2985 | 55.75% | 54.54% | 1.23 | 1.17 |  | -0.06 | 66.67% |  |
| i02-low-vol-level-week | week | bullish | 1300 | 50.69% | 48.85% | 1.85 | 1.17 |  | -0.33 | 60.00% |  |
| f04-open-volume-corr-day | day | bullish | 7335 | 45.59% | 44.96% | 0.63 | 1.17 |  | -0.49 | 83.33% |  |
| t06-bollinger-pctb-day | day | bullish | 4239 | 46.71% | 44.76% | 1.04 | 1.14 |  | -0.63 | 66.67% |  |
| t21-minervini-template-week | week | bullish | 1261 | 50.44% | 48.67% | 1.66 | 1.13 |  | -0.73 | 80.00% |  |
| t03-rsi-thresholds-day | day | bearish | 5109 | 56.12% | 54.88% | 0.89 | 1.12 |  | -0.04 | 83.33% |  |
| o03-trend-confirmed-day | day | bearish | 4508 | 55.08% | 54.42% | 0.90 | 1.08 |  | -0.13 | 66.67% |  |
| t23-rs-rating-week | week | bearish | 1300 | 52.38% | 50.96% | 1.42 | 1.03 |  | -0.21 | 60.00% |  |
| f07-high-push-fade-day | day | bullish | 6982 | 45.55% | 44.92% | 0.61 | 1.02 |  | -0.55 | 66.67% |  |
| t03-rsi-thresholds-week | week | bearish | 1099 | 51.87% | 51.07% | 1.72 | 1.02 |  | -0.06 | 66.67% |  |
| a07c-volume-fade-week | week | bearish | 1510 | 52.19% | 50.84% | 1.34 | 1.00 |  | 0.03 | 66.67% | candidate |
| c03-pre-holiday-day | day | bearish | 300 | 57.33% | 55.13% | 2.21 | 0.99 |  | 0.01 | 60.00% | too few picks |
| o01-retest-day | day | bearish | 5641 | 54.85% | 54.31% | 0.66 | 0.95 |  | -0.12 | 50.00% |  |
| t07-bollinger-squeeze-breakout-week | week | bearish | 10 | 60.00% | 48.72% | 11.28 | 0.91 |  | -0.52 | 83.33% | too few picks |
| i01-momentum-score-week | week | bullish | 1300 | 50.08% | 48.85% | 1.23 | 0.85 |  | -0.62 | 80.00% |  |
| a09-gap-fade-day | day | bullish | 3065 | 45.51% | 44.58% | 0.87 | 0.83 |  | -0.51 | 66.67% |  |
| f02-volume-signed-reversal-day | day | bullish | 7335 | 45.41% | 44.96% | 0.46 | 0.82 |  | -0.57 | 66.67% |  |
| a07c-volume-fade-week | week | bullish | 1510 | 49.87% | 48.97% | 0.90 | 0.79 |  | -0.52 | 50.00% |  |
| t18-ichimoku-cloud-week | week | bearish | 1405 | 51.81% | 50.67% | 1.06 | 0.78 |  | -0.27 | 50.00% |  |
| t02-golden-death-cross-week | week | bullish | 1355 | 49.96% | 48.87% | 1.09 | 0.77 |  | -0.54 | 50.00% |  |
| t22-vcp-week | week | bullish | 52 | 51.92% | 47.05% | 5.03 | 0.70 |  | -0.32 | 60.00% | too few picks |
| e2b-day | day | bullish | 1853 | 47.71% | 44.91% | 0.88 | 0.65 |  | -0.41 | 50.00% |  |
| a03-momentum-12-1-week | week | bearish | 1275 | 51.45% | 50.60% | 0.85 | 0.61 |  | -0.26 | 40.00% |  |
| q03-up-day-balance-week | week | bullish | 1542 | 49.48% | 48.89% | 0.69 | 0.55 |  | -0.58 | 83.33% |  |
| t09-supertrend-day | day | bearish | 7127 | 54.72% | 54.40% | 0.32 | 0.53 |  | -0.05 | 50.00% |  |
| o04b-no-d01-day | day | bearish | 5641 | 54.44% | 54.31% | 0.33 | 0.47 |  | -0.16 | 50.00% |  |
| f05-close-location-change-day | day | bearish | 7333 | 54.77% | 54.54% | 0.23 | 0.42 |  | -0.14 | 33.33% |  |
| o04b-no-d01-day | day | bullish | 6673 | 45.44% | 45.06% | 0.23 | 0.39 |  | -0.58 | 83.33% |  |
| g05-residual-reversal-week | week | bullish | 1495 | 49.23% | 48.84% | 0.40 | 0.34 |  | -0.54 | 50.00% |  |
| champion-v1-week | week | bearish | 1515 | 51.29% | 50.88% | 0.41 | 0.33 |  | -0.01 | 50.00% |  |
| f01-body-share-day | day | bearish | 7331 | 54.69% | 54.54% | 0.17 | 0.30 |  | -0.07 | 50.00% |  |
| o05-order-block-weekly-week | week | bearish | 1088 | 50.18% | 50.45% | 0.32 | 0.21 |  | -0.31 | 60.00% |  |
| e1a-day | day | bullish | 335 | 48.06% | 44.28% | 0.59 | 0.20 |  | -0.47 | 33.33% | too few picks |
| t07-bollinger-squeeze-breakout-week | week | bullish | 18 | 44.44% | 45.08% | 1.79 | 0.17 |  | -0.46 | 66.67% | too few picks |
| a03-momentum-12-1-week | week | bullish | 1275 | 49.41% | 49.20% | 0.21 | 0.15 |  | -0.57 | 60.00% |  |
| o01-retest-week | week | bearish | 1183 | 51.65% | 50.92% | 0.18 | 0.12 |  | -0.11 | 50.00% |  |
| a06-low-volatility-week | week | bearish | 1469 | 50.99% | 50.72% | 0.15 | 0.12 |  | -0.02 | 50.00% |  |
| q02-return-volume-corr-day | day | bearish | 7325 | 54.58% | 54.53% | 0.05 | 0.09 |  | -0.07 | 50.00% |  |
| a08-overnight-intraday-tug-day | day | bullish | 7315 | 44.99% | 44.96% | 0.04 | 0.07 |  | -0.51 | 16.67% |  |
| d02-stock-pcr-confirmatory-week | week | bearish | 1246 | 49.76% | 50.75% | 0.04 | 0.03 |  | -0.39 | 50.00% |  |
| t16-parabolic-sar-week | week | bearish | 1440 | 50.69% | 50.68% | 0.01 | 0.01 |  | -0.26 | 33.33% |  |
| o02-oi-confirmed-day | day | bearish | 1982 | 54.34% | 54.67% | 0.01 | 0.01 |  | -0.09 | 50.00% |  |
| o04a-no-volume-week | week | bearish | 1183 | 51.39% | 50.92% | -0.03 | -0.02 |  | -0.07 | 16.67% |  |
| a01-weekly-reversal-week | week | bullish | 1545 | 48.87% | 48.89% | -0.03 | -0.02 |  | -0.51 | 50.00% |  |
| t21-minervini-template-week | week | bearish | 1235 | 51.82% | 51.34% | -0.05 | -0.03 |  | -0.17 | 80.00% |  |
| t05-macd-crossover-day | day | bearish | 4871 | 54.18% | 54.68% | -0.06 | -0.07 |  | -0.04 | 50.00% |  |
| f06-trend-acceleration-week | week | bullish | 1544 | 48.77% | 48.89% | -0.09 | -0.08 |  | -0.56 | 33.33% |  |
| t09-supertrend-week | week | bearish | 1504 | 50.66% | 50.76% | -0.11 | -0.08 |  | -0.14 | 50.00% |  |
| t11-inside-bar-day | day | bearish | 6054 | 54.38% | 54.62% | -0.08 | -0.12 |  | -0.11 | 66.67% |  |
| t03-rsi-thresholds-week | week | bullish | 1030 | 48.74% | 48.75% | -0.33 | -0.20 |  | -0.41 | 50.00% |  |
| a05-max-effect-week | week | bearish | 1475 | 50.37% | 50.65% | -0.28 | -0.22 |  | -0.37 | 50.00% |  |
| a05b-max-effect-ranked-week | week | bearish | 1475 | 50.37% | 50.65% | -0.28 | -0.22 |  | -0.37 | 50.00% |  |
| q05-trend-smoothness-week | week | bullish | 1529 | 48.66% | 48.89% | -0.33 | -0.24 |  | -0.55 | 50.00% |  |
| d02-stock-pcr-contrarian-week | week | bullish | 1246 | 49.92% | 49.05% | -0.38 | -0.28 |  | -0.28 | 33.33% |  |
| q04-range-extreme-timing-week | week | bullish | 1493 | 48.83% | 49.05% | -0.42 | -0.30 |  | -0.81 | 50.00% |  |
| o04-order-block-composite-week | week | bearish | 1183 | 50.89% | 50.92% | -0.44 | -0.32 |  | -0.06 | 16.67% |  |
| a04-52-week-high-week | week | bearish | 1300 | 50.46% | 50.96% | -0.50 | -0.36 |  | -0.34 | 40.00% |  |
| t14-cci-week | week | bullish | 962 | 46.78% | 48.51% | -0.63 | -0.36 |  | -0.50 | 50.00% |  |
| t10-nr4-narrow-range-day | day | bearish | 6586 | 54.43% | 54.61% | -0.23 | -0.37 |  | -0.11 | 50.00% |  |
| t12-stochastic-day | day | bearish | 4748 | 54.65% | 54.78% | -0.31 | -0.40 |  | -0.09 | 50.00% |  |
| t16-parabolic-sar-day | day | bearish | 6830 | 54.20% | 54.44% | -0.23 | -0.40 |  | -0.11 | 50.00% |  |
| q01-price-volume-corr-week | week | bearish | 1478 | 50.20% | 50.95% | -0.58 | -0.44 |  | -0.23 | 16.67% |  |
| t08-donchian-breakout-55-week | week | bearish | 905 | 50.50% | 50.95% | -0.90 | -0.48 |  | -0.44 | 50.00% |  |
| t23-rs-rating-week | week | bullish | 1300 | 48.15% | 48.85% | -0.69 | -0.49 |  | -0.76 | 40.00% |  |
| t13-williams-r-day | day | bullish | 7046 | 44.64% | 44.92% | -0.28 | -0.49 |  | -0.58 | 50.00% |  |
| o03-trend-confirmed-week | week | bearish | 955 | 50.99% | 51.40% | -0.91 | -0.52 |  | -0.19 | 33.33% |  |
| o04a-no-volume-day | day | bearish | 5641 | 53.57% | 54.31% | -0.37 | -0.53 |  | -0.15 | 33.33% |  |
| o00-placebo-week | week | bullish | 1505 | 48.44% | 49.05% | -0.61 | -0.55 |  | -0.51 | 50.00% |  |
| o03-trend-confirmed-day | day | bullish | 5975 | 44.45% | 44.97% | -0.36 | -0.55 |  | -0.59 | 16.67% |  |
| t11-inside-bar-day | day | bullish | 6231 | 44.97% | 44.90% | -0.37 | -0.56 |  | -0.54 | 16.67% |  |
| t25-heikin-ashi-day | day | bearish | 4997 | 54.31% | 54.26% | -0.44 | -0.57 |  | -0.07 | 50.00% |  |
| t17-keltner-breakout-week | week | bearish | 919 | 50.71% | 51.66% | -1.18 | -0.68 |  | -0.14 | 50.00% |  |
| a07-high-volume-premium-week | week | bearish | 1510 | 50.00% | 50.84% | -0.84 | -0.74 |  | -0.14 | 50.00% |  |
| t10-nr7-narrow-range-day | day | bearish | 5756 | 54.57% | 54.60% | -0.55 | -0.79 |  | -0.09 | 16.67% |  |
| o01-retest-day | day | bullish | 6673 | 44.69% | 45.06% | -0.47 | -0.80 |  | -0.60 | 50.00% |  |
| o04b-no-d01-week | week | bearish | 1183 | 50.04% | 50.92% | -1.12 | -0.81 |  | -0.10 | 16.67% |  |
| t15-adx-regime-week | week | bullish | 1452 | 47.59% | 48.57% | -1.15 | -0.87 |  | -0.98 | 33.33% |  |
| e1b-day | day | bullish | 3123 | 45.44% | 45.03% | -0.91 | -0.87 |  | -0.63 | 50.00% |  |
| f06-trend-acceleration-day | day | bullish | 7320 | 44.49% | 44.96% | -0.50 | -0.89 |  | -0.63 | 66.67% |  |
| q03-up-day-balance-day | day | bullish | 7314 | 44.44% | 44.96% | -0.52 | -0.90 |  | -0.60 | 33.33% |  |
| t14-cci-week | week | bearish | 1109 | 49.86% | 51.75% | -1.61 | -0.91 |  | -0.15 | 16.67% |  |
| o04-order-block-composite-day | day | bearish | 5641 | 53.24% | 54.31% | -0.65 | -0.93 |  | -0.18 | 33.33% |  |
| t25-heikin-ashi-week | week | bearish | 1051 | 50.71% | 50.51% | -1.49 | -0.94 |  | -0.03 | 33.33% |  |
| q07-trend-residual-week | week | bullish | 1541 | 47.57% | 48.89% | -1.19 | -0.94 |  | -0.77 | 33.33% |  |
| t19-obv-divergence-week | week | bullish | 1503 | 47.84% | 48.87% | -1.20 | -1.03 |  | -0.72 | 50.00% |  |
| t15-adx-regime-day | day | bullish | 6891 | 44.26% | 44.93% | -0.64 | -1.04 |  | -0.62 | 50.00% |  |
| a07-high-volume-premium-week | week | bullish | 1510 | 47.55% | 48.97% | -1.42 | -1.06 |  | -0.69 | 33.33% |  |
| a02-extreme-day-reversal-day | day | bullish | 3223 | 45.36% | 44.96% | -1.10 | -1.07 |  | -0.63 | 50.00% |  |
| o03-trend-confirmed-week | week | bullish | 1270 | 47.80% | 48.79% | -1.45 | -1.11 |  | -0.55 | 33.33% |  |
| t18-ichimoku-cloud-week | week | bullish | 1400 | 47.29% | 49.30% | -1.56 | -1.13 |  | -0.66 | 33.33% |  |
| o00-placebo-day | day | bearish | 7125 | 53.73% | 54.40% | -0.65 | -1.20 |  | -0.16 | 16.67% |  |
| f05-close-location-change-day | day | bullish | 7334 | 44.29% | 44.96% | -0.66 | -1.22 |  | -0.60 | 50.00% |  |
| e2a-day | day | bullish | 2149 | 44.25% | 44.20% | -1.58 | -1.25 |  | -0.74 | 33.33% |  |
| t17-keltner-breakout-week | week | bullish | 1054 | 46.77% | 48.47% | -2.20 | -1.25 |  | -0.91 | 16.67% |  |
| o00-placebo-week | week | bearish | 1500 | 49.20% | 50.76% | -1.48 | -1.27 |  | -0.33 | 50.00% |  |
| o04b-no-d01-week | week | bullish | 1418 | 47.95% | 49.11% | -1.68 | -1.35 |  | -0.48 | 16.67% |  |
| t03-rsi-thresholds-day | day | bullish | 4896 | 44.40% | 44.95% | -1.13 | -1.38 |  | -0.59 | 33.33% |  |
| f03-conditional-reversal-day | day | bullish | 7334 | 44.18% | 44.96% | -0.77 | -1.39 |  | -0.66 | 50.00% |  |
| t01-sma-crossover-week | week | bullish | 1499 | 47.10% | 48.80% | -1.81 | -1.45 |  | -1.09 | 33.33% |  |
| q02-return-volume-corr-week | week | bullish | 1545 | 46.99% | 48.89% | -1.90 | -1.58 |  | -0.51 | 33.33% |  |
| t14-cci-day | day | bearish | 5285 | 53.59% | 54.82% | -1.29 | -1.74 |  | -0.09 | 16.67% |  |
| c02-turn-of-month-week | week | bearish | 885 | 49.15% | 51.87% | -2.72 | -1.74 |  | -0.45 | 25.00% |  |
| o00-placebo-day | day | bullish | 7107 | 44.15% | 45.06% | -0.95 | -1.75 |  | -0.56 | 16.67% |  |
| d02-stock-pcr-confirmatory-week | week | bullish | 661 | 45.54% | 48.88% | -3.99 | -1.76 |  | -0.83 | 16.67% |  |
| q02-return-volume-corr-day | day | bullish | 7325 | 43.99% | 44.96% | -0.97 | -1.79 |  | -0.61 | 16.67% |  |
| o04a-no-volume-day | day | bullish | 6673 | 44.04% | 45.06% | -1.08 | -1.79 |  | -0.62 | 16.67% |  |
| t08-donchian-breakout-20-week | week | bearish | 1218 | 48.93% | 50.68% | -2.72 | -1.80 |  | -0.38 | 16.67% |  |
| o01-retest-week | week | bullish | 1418 | 47.39% | 49.11% | -2.21 | -1.86 |  | -0.50 | 16.67% |  |
| o04-order-block-composite-day | day | bullish | 6673 | 43.95% | 45.06% | -1.16 | -1.93 |  | -0.62 | 16.67% |  |
| q01-price-volume-corr-day | day | bullish | 7214 | 43.73% | 44.99% | -1.13 | -2.02 |  | -0.61 | 16.67% |  |
| champion-v1-week | week | bullish | 1508 | 45.95% | 48.93% | -2.82 | -2.06 |  | -0.78 | 16.67% |  |
| c01-day-of-week-day | day | bearish | 6900 | 53.25% | 54.39% | -1.15 | -2.07 |  | -0.18 | 33.33% |  |
| o04a-no-volume-week | week | bullish | 1418 | 46.69% | 49.11% | -2.88 | -2.38 |  | -0.73 | 16.67% |  |
| t05-macd-crossover-week | week | bullish | 1028 | 46.60% | 49.08% | -3.90 | -2.39 |  | -0.90 | 16.67% |  |
| t09-supertrend-week | week | bullish | 1498 | 45.99% | 49.05% | -3.18 | -2.39 |  | -0.67 | 16.67% |  |
| o04-order-block-composite-week | week | bullish | 1418 | 46.61% | 49.11% | -2.95 | -2.39 |  | -0.73 | 16.67% |  |
| t01-sma-crossover-day | day | bullish | 7114 | 43.59% | 44.99% | -1.46 | -2.48 |  | -0.67 | 0.00% |  |
| champion-v1-day | day | bullish | 7137 | 43.51% | 45.00% | -1.55 | -2.51 |  | -0.61 | 16.67% |  |
| q01-price-volume-corr-day | day | bearish | 7004 | 52.96% | 54.60% | -1.51 | -2.51 |  | -0.15 | 16.67% |  |
| t24-pivot-points-day | day | bearish | 7322 | 53.02% | 54.54% | -1.47 | -2.60 |  | -0.12 | 16.67% |  |
| t08-donchian-breakout-20-week | week | bullish | 1363 | 45.49% | 48.91% | -3.97 | -2.68 |  | -0.89 | 33.33% |  |
| q01-price-volume-corr-week | week | bullish | 1524 | 45.34% | 48.89% | -3.39 | -2.92 |  | -0.79 | 0.00% |  |
| t16-parabolic-sar-week | week | bullish | 1440 | 45.14% | 49.13% | -3.99 | -2.98 |  | -0.96 | 16.67% |  |
| t14-cci-day | day | bullish | 4552 | 43.41% | 45.02% | -2.44 | -3.02 |  | -0.56 | 0.00% |  |
| t08-donchian-breakout-55-week | week | bullish | 1169 | 44.48% | 48.79% | -5.09 | -3.09 |  | -0.98 | 16.67% |  |
| a10-gap-and-go-day | day | bullish | 1006 | 37.38% | 43.21% | -5.41 | -3.10 |  | -0.81 | 0.00% |  |
| t16-parabolic-sar-day | day | bullish | 6825 | 43.15% | 45.05% | -1.88 | -3.26 |  | -0.61 | 0.00% |  |
| t05-macd-crossover-day | day | bullish | 4819 | 42.04% | 44.54% | -2.86 | -3.59 |  | -0.61 | 16.67% |  |
| t20-volume-breakout-day | day | bullish | 3754 | 41.88% | 44.71% | -3.75 | -4.02 |  | -0.61 | 0.00% |  |
| t09-supertrend-day | day | bullish | 7089 | 42.71% | 45.09% | -2.51 | -4.36 |  | -0.67 | 16.67% |  |
| d01-oi-buildup-day | day | bearish | 7334 | 52.06% | 54.54% | -2.48 | -4.59 |  | -0.15 | 0.00% |  |
| o02-oi-confirmed-day | day | bullish | 2421 | 39.98% | 44.54% | -5.15 | -4.60 |  | -0.68 | 16.67% |  |
| f01-body-share-day | day | bullish | 7317 | 42.27% | 44.93% | -2.70 | -4.85 |  | -0.64 | 0.00% |  |
| t12-stochastic-day | day | bullish | 4153 | 42.43% | 44.85% | -4.53 | -5.23 |  | -0.66 | 0.00% |  |
| d01-oi-buildup-day | day | bullish | 7304 | 40.32% | 44.93% | -4.61 | -8.15 |  | -0.75 | 0.00% |  |
| t24-pivot-points-day | day | bullish | 7306 | 39.95% | 44.91% | -4.94 | -8.51 |  | -0.73 | 0.00% |  |
| c03-pre-holiday-day | day | bullish | 5 | 0.00% | 21.54% | -21.54 | n/a |  | -3.24 | 0.00% | too few picks |
