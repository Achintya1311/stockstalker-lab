# StockStalker Lab: specification

Status: final as of 16 Oct 2026. This file is the contract the lab routine works to. Changing it means changing a protected path (see `PROTECTED.txt`).

## 1. What the lab does

It researches, builds, tunes and tests rule-based strategies that pick NSE F&O stocks, bullish or bearish, on two horizons:

- **Day:** today's open to today's close.
- **Week:** Monday's open to Friday's close.

It keeps a roster of at most 12 strategies that pass the gates in section 6. Each strategy is scored on its own. The public picks are drawn from the roster.

It runs every 2 hours, on its own, with no human approval step. Code-enforced gates take the place of a human reviewer.

## 2. Market and universe

- **Instruments:** NSE stocks and their stock futures only. No options, index or commodities.
- **Universe on date *d*:** the stocks with an active stock future (FUTSTK) in that day's NSE F&O bhavcopy, so membership is point-in-time.
- **Prices:** NSE equity bhavcopy, EQ series, which includes names later delisted or merged.
- **Adjustments:** split and bonus adjustment factors come from the bhavcopy's PREVCLOSE (the exchange's adjusted base price) divided by the previous day's CLOSE. Indicators use adjusted series. Day open-to-close moves need no adjustment.
- **Liquidity floor:** 20-day median turnover of at least ₹25 cr (in `config/universe.yml`).
- **Futures:** a short is realistic only through stock futures. Hit or miss is scored on the underlying stock's move, which futures track.

## 3. Scoring

- **Hit:** the move from open to close is strictly in the picked direction. No move at all (close equals open) counts as a miss.
- **Market line, per date, horizon and side:** for bullish picks, the share of the universe that rose; for bearish picks, the share that fell.
- **Edge** = hit rate − market line, averaged over the same dates.
- **Directional move** = the mean of (move × side), after costs:
  - delivery: 0.1% STT on each side plus 0.015% stamp duty
  - futures: 0.05% STT on the sell leg
  - 10 bps slippage either way

  This is used internally only, so that a strategy can't be "right" through tiny moves while its misses are large.
- **Random baseline:** where the strategy's hit rate ranks among 1,000 random pick lists of the same size, drawn from the same universe on the same dates.
- **Selective strategies** may abstain on a date. Their coverage (the share of dates with picks) is always reported next to their accuracy.

## 4. Splits (fixed; changing them breaks every comparison)

| Split | Dates | Use |
|---|---|---|
| Train | 2015-01-01 to 2020-12-31 | Unlimited. Build, tune, ablate here |
| Validation | 2021-01-01 to 2023-12-31 | Only through the reusable holdout (Thresholdout, Dwork et al. 2015): noisy pass/fail answers, at most 60 queries a week |
| Test | 2024-01-01 to 2026-07-31 | Promotion job only, at most 2 looks a week, every look logged in `ledger/test_looks.csv` |
| Exam | 2026-08-01 to go-live | Run once by the roster frozen at go-live. Published as "backtest on unseen data" |
| Live | Go-live onward | Picks committed before 09:15 IST, scored after the close |

**Replay engine (`engine/`):**
- It steps through dates. A strategy receives only data up to the previous close (Friday's close for week picks), as a truncated slice.
- Picks are appended to a log and hashed before outcomes are loaded.
- Any strategy parameter that is learned is re-learned walk-forward, from past data only.
- The engine refuses dates outside the split a job is authorised for.

## 5. Strategies

- **Interface:** `score(history: pd.DataFrame) -> pd.Series` (one score per symbol; NaN means abstain), plus a `rules_fired(history, symbol) -> str` for the reasoning column.
- **Required for every strategy:**
  - `audit.py` causality check
  - a synthetic unit test with a known expected signal
  - attribution in its header
- **Sources:** each idea becomes a `cards/<id>.yml` card with these fields: `source_url`, `author`, `license`, `published_on`, `claim_as_stated`, `horizon`, `rules_plain`, `params`, `red_flags`, `status`.
- **No claim is assumed true.** Every card's claim is tested on NSE data and marked `confirmed` or `refuted`, with the numbers.
- **Idea vintage:** an idea published in year Y is only truly out-of-sample after Y. Where possible, its post-publication record is reported separately.
- **Sources kept open (read only; nothing is ever posted):**
  - Quantpedia (free strategies), SSRN, Chen–Zimmermann open-source asset pricing, the *101 Formulaic Alphas* paper, the Nifty200 Momentum 30 method, IIMA factors
  - PKScreener (MIT), Screeni-py (MIT), Microsoft Qlib Alpha158 (MIT), Microsoft RD-Agent(Q) for loop design, alphalens-reloaded (Apache-2.0) for evaluation ideas, pandas-ta and TA-Lib for indicator definitions
  - QuantDinger (Achintya's fork; check its licence before copying), WorldQuant BRAIN public materials
  - TradingView open-source scripts (MPL-2.0; each ported file keeps an MPL-2.0 header)
  - r/algotrading, r/quant, r/IndianStockMarket, r/IndianStreetBets, TradingQnA, QuantConnect forum, Elite Trader
  - existing threads that critique backtests, which become methodology checklist items
- **Licence care:** backtesting.py is AGPL. Read it, but don't copy code from it.

## 6. Gates: when a strategy joins the roster

Every gate is checked separately for each horizon and side. A strategy needs all of these on **test**:

1. Edge of at least 5 points over the market line.
2. A trial-corrected significance of t ≥ 3, where the trial count is the cumulative count in `ledger/trials.csv`. The bar rises as more is tried.
3. Positive edge in at least 70% of calendar years across train, validation and test.
4. At least 500 test picks.
5. Directional move greater than 0 after costs.
6. It beats at least 95% of random lists.
7. It survives parameter nudges: ±10% on each trigger value keeps edge ≥ 3 points.
8. Pick overlap with every current roster member below 50%.

On top of the gates:
- **High-conviction tag:** a strategy is tagged if, on selective picks only, its test hit rate is at least 75% with at least 200 picks. Its coverage is shown.
- **Leak alarm:** any strategy with long-sample accuracy of 70% or more, or edge of 15 points or more, is quarantined until it passes two re-runs: outcomes shifted by +1 day, and outcomes shuffled within each date. Its edge must collapse in both.

## 7. Roster, versions, deterioration

- **Roster size:** at most 12. A newcomer replaces the weakest member only if it passes every gate and beats that member on test.
- **Versions** are immutable (`strategy_id@vN`). A new version never overwrites an old one.
- **When the roster changes:** Sundays only, so each week's tables come from one roster.
- **Live decay monitor:** a sequential test (CUSUM) on the edge over the market line.
  - On a confirmed decay, the strategy is demoted to `watch`: still scored, but no longer shown.
  - If a new version does worse live than its predecessor over at least 100 picks, it is automatically rolled back.
- **Decay concentrated in one regime** (VIX bucket, market trend) becomes a new card proposing a regime filter.
- **Retired strategies** keep their full public record.

## 8. Tuning trigger values

- Tuning happens on **train only**, with a coarse grid or Optuna (a fixed trial budget per run).
- Choose the middle of the widest stable region, not the single best value. A value that only works at one exact setting is rejected.
- Re-tune walk-forward every 12 months of replay.
- Every grid point counts as a trial.

## 9. Routine: lanes instead of a lock

Every 2 hours (`7 */2 * * *`, Sonnet). A run claims a **lane** by committing `state/leases/<lane>.json` with an expiry 100 minutes out. If the push races and loses, the run takes the next free lane. A run that overlaps an active one therefore does different work. The lanes are:

| Lane | Parallel? | Writes |
|---|---|---|
| `discover` | yes, several | new `cards/*.yml`, `research/notes/*.md` |
| `tune` | yes, one per strategy | branch `tune/<id>`, train-only results |
| `port` | yes, one per card | branch `port/<card>`, code plus tests |
| `diagnose` | yes | `research/diagnostics/*.md`, new cards |
| `evaluate` | **exclusive** | holdout queries, test looks, roster changes, `ledger/` |
| `live` | **exclusive**, after 15:45 IST on trading days | scoring of live picks, decay monitor |

**Every run:**
1. Read `state/journal.md`, `state/queue.md` and the ledger.
2. Claim a lane and do one unit of work.
3. Append a journal entry: hypothesis, result, next.
4. Open a PR.

Auto-merge requires green checks: tests, audit, protected paths untouched, budgets respected.

The routine never edits protected paths, never posts anywhere, and never uses paid services. Engine problems go to `state/engine-issues.md` for a supervised session.

## 10. Publishing (Achintya's decision, 16 Oct 2026)

- Four tables: Day Bullish, Day Bearish, Week Bullish, Week Bearish. Five picks each, drawn from the roster consensus.
  - Columns: Stock, Reasoning (which strategies picked it and the rules that fired), Open, Close, Move (% and ₹).
  - Move is green when the direction was right and red when wrong, with ▲/▼ arrows.
- Real picks are published before the open, with: "Model output in testing. Not investment advice or a recommendation. Not a SEBI-registered research analyst. Every pick is shown, including misses."
- No entry, target or stop prices. No buy/sell words. No P&L. No follower channel.
- **Headline accuracy is out-of-sample:** "Test 2024–Jul 2026: x% vs market y%", then exam, then live. Any full 2015–2026 figure is labelled "includes training years".
- Per-strategy leaderboard, plus the retired strategies.
- Generated by GitHub Actions into `live/*.json`. The site renders it later.
