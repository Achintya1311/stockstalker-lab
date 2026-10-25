# Calendar family (C01-C04): diagnosis

Train split, `top` selection. Replays: `experiments/done/c01-day-of-week-day/`, `c02-turn-of-month-week/`,
`c03-pre-holiday-day/`, `c04-expiry-week-{day,week}/`. Per-card notes: `c01.md` to `c04.md`.

## The finding: these cards do not test their calendar effect

Every calendar card gives **one market-wide score to every symbol on a date** (checked in `picks.json`:
1,380 of 1,380 C01 dates, 185 of 185 C02 dates and 61 of 61 C03 dates carry a single score value). Two
consequences follow, and together they mean the replays measure something other than the card's claim.

1. **The top 5 picks are the alphabetically first five in-universe symbols.** `engine/experiment_report.select`
   breaks ties in `|score|` by symbol name, so when every score is equal the "best five" is always the
   same handful of A-names. Each card's `top` numbers are a test of those five stocks, not of the
   weekday, month turn, holiday or expiry week.
2. **The sign is almost never bullish.** Each card's score is the bucket's mean open-to-close return,
   uncentred. NSE F&O stocks close below their open more often than not (the day market line is 44-46%
   up in every train year, `reports/market_line_train.md`), so nearly every bucket mean is negative. C01
   never fired bullish on any of 1,380 dates; C02 fired bullish on 8 of 185; C03 on 1 of 61. This is the
   same "uncentred score" defect A05 v1 had (`a05.md`).

The `all` selection avoids problem 1 but not problem 2: it is "every stock, one side", so its accuracy
equals the market line by construction and its edge is 0.00 (C01 all-bearish: 197,321 picks, edge -0.00).

## Numbers, for the record (they do not bear on the claims)

| Card | Side fired | Dates | Edge | t | Dir. move after costs |
|---|---|---|---|---|---|
| C01 day of week (day) | bearish only | 1,380 | -1.15 | -2.07 | -0.18% |
| C02 turn of month (week) | bearish (177), bullish (8) | 185 | -2.72 / +11.87 (8 dates) | -1.74 / 1.38 | -0.45% / +0.77% |
| C03 pre-holiday (day) | bearish (60), bullish (1) | 61 | +2.21 / -21.54 (1 date) | 0.99 / n/a | +0.01% / -3.24% |
| C04 expiry week (day, week) | none | 0 | n/a | n/a | n/a |

C04 produced **zero picks** on both horizons. Its unit tests pass on synthetic data, so the cause is in
how it meets the real dataset: most likely `expiry_futstk` is missing or empty in the cached parquet, or
its dates fail to line up with the pooled-return index, so `_bias_for_history` abstains every date. This
can't be checked from the sandbox (no dataset). `c04.md` gives the check to run.

## None is a go-live P1 candidate

No card clears SPEC.md section 10's provisional rule on a real test of its claim. C03-bearish's
+2.21 / +0.01% is five alphabetical stocks on 60 pre-holiday days, not a pre-holiday effect.

## What to try next

- **Retire the stand-alone calendar cards as stock pickers.** A market-wide tilt cannot rank stocks, so
  it can never fill a five-stock table by itself. Their natural use is as a **filter or regime input**
  (P4): "publish the bullish table's picks only on days the calendar bucket is above its own average",
  applied to a strategy that already ranks stocks.
- If a calendar card is re-tested on its own, centre it (bucket mean minus the all-days mean) so it can
  point both ways, and score it on the `all` selection's per-date mean move rather than a top-5 table.
- C04: find out why it abstains everywhere before building on it (see `c04.md`).
