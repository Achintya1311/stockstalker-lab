# Third-party reference code (read only, never imported)

Copied unmodified so the lab can study and port rules without network access. Each folder keeps its original licence. Ported code in `strategies/` names the file and function it came from.

| Folder | Source | Commit | Licence | What it is |
|---|---|---|---|---|
| `pkscreener/` | https://github.com/pkjmesra/PKScreener | `ab4212355e24` | MIT | `ScreeningStatistics.py` holds about 95 `find*`/`validate*` scanners (breakouts, VCP, NR4, inside bar, RSI/MACD crosses, ATR trailing stops, short-sell candidates). `Pktalib.py` wraps the indicators, and `Backtest.py` is its forward-return backtest |
| `qlib/` | https://github.com/microsoft/qlib | `543552324638` | MIT | `loader.py` holds `Alpha158DL.get_feature_config`: the 158 price/volume feature formulas (KMID, ROC, MA, STD, CORR, and so on) |

Not copied, on purpose:
- Papers and books: cite and link them only.
- backtesting.py: AGPL.
- TradingView scripts: these go one file per port with an MPL-2.0 header.
- Forum posts: summarised in our own words in `cards/catalog.csv`.
