# StockStalker Lab

An autonomous research lab that builds, tunes and tests rule-based strategies picking NSE F&O stocks, bullish or bearish, a day or a week ahead. It keeps only the strategies that beat the market's own base rate on data they have never seen.

Read [SPEC.md](SPEC.md) first. It defines the market, how picks are scored, the train/validation/test splits, the gates a strategy must pass, and how the lab runs.

**Status:** building. The engine and its guardrails come first; the autonomous loop starts only once they pass their own tests.

> Model research in testing. Not investment advice or a recommendation. The author is not a SEBI-registered research analyst. Every pick is shown, including misses.

Part of the [StockStalker](https://github.com/Achintya1311/STOCKSTALKER) project.
