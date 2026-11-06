# E2A_F11_FB: E2A first, F11 on the dates E2A has no tradable pick (day-bearish): diagnosis

Train split (2015-01-01 to 2020-12-31), day horizon, `top` selection. Replay:
`experiments/done/e2a-f11-fallback-day/` (landed 7d54967). Card: `cards/E2A_F11_FB.yml` (pre-declared 6 Nov, 5d81027).
Joint test: `reports/evidence_train.md` (day/bearish, 58 experiments, 08d5366).

## Pre-declared rule: met on every part

| Strategy | Picks | Dates with picks | Edge | t | 95% interval | Dir. move after costs | Positive years |
|---|---|---|---|---|---|---|---|
| E2A | 2,767 | 936 (64%) | +7.46 | 6.92 | +5.27 to +9.67 | +0.13% | 6/6 |
| E2A_D01C_FB | 4,996 | 1,386 (94%) | +5.97 | 7.44 | +4.37 to +7.57 | +0.06% | 6/6 |
| **E2A_F11_FB** | **5,442** | **1,467 (100%)** | **+6.38** | **8.34** | **+4.84 to +7.88** | **+0.06%** | **6/6** |

Rule: edge at least +5.97 (**+6.38, met**), interval above 0 (**met**), 5 of 6 years (**6/6, met**), dir at least +0.06%
(**+0.062%, met by a hair**), coverage at least 99% (**100%, met**). Prediction ranges: edge +5.3 to +6.6 held, dir
+0.04% to +0.12% held, switching to F11 on 33 to 40% of dates held (545 of 1,476 pick-log dates, 37%).

Per-year edge 2015-2020: +2.73, +7.87, +5.41, +3.72, +9.27, +8.98 (E2A_D01C_FB: +2.17, +7.48, +6.28, +4.87, +6.47,
+8.06). Better in 2015, 2016, 2019 and 2020, worse in 2017 and 2018.

## Where it works and fails

- **F11 holds its level on E2A's quiet dates; D01C did not.** Backing out the F11 dates from the totals (approximate:
  it assumes E2A's 931 dates carry E2A's own +7.46 and +0.13%), F11 on the remaining ~536 scored dates reads about
  +4.5, its all-dates level (+4.47), against D01C's ~+2.9 there. The directional move on those dates is about -0.01%:
  F11 calls the direction but the moves are small, which is why the total dir only just clears +0.06%.
- **The tradable switch closed the coverage gap.** E2A scores some stock bearish on 1,015 pick-log dates; on 84 of
  them none of those stocks was in the universe at the last close, and this card read F11 instead of leaving an empty
  table. Every scored date has picks (1,467 of 1,467), against 1,386 for E2A_D01C_FB. The replay cannot separate the
  two changes; the coverage gain is the switch's, the edge gain on the quiet dates is F11's.
- **2017-18 are the weak years.** The years mid caps fell while a few large caps rose are where F11 lags D01C as a
  fallback; the same 2017-18 weakness shows in H01, F12 and F08.
- **Joint test.** StepM names it individually superior, and it is one of 3 in the day-bearish MCS of 58 (with D01C and
  E2A_D01C_FB). Dates with no pick count as edge 0 in the joint tests, which is why E2A itself is outside the MCS.

## Go-live

It meets the provisional letter on day-bearish (5,442 picks, +6.38, +0.06%) and its card's helps rule. It does not
change the table: SPEC 10 moves day bearish off E2A (released +6.72) only for a released edge of at least +7.72, and
a blend of E2A with a +4.5 member is not expected to release that much. As pre-declared, no validation query is spent.
What it offers is coverage: the live day-bearish table has had 2 to 5 picks a day since 2 Nov and is empty on dates
E2A does not fire; this card fills every date for about 1.1 points of train edge. That trade is not something the
letter of SPEC 10 rewards, so it is written up for a supervised decision in `state/engine-issues.md`.

## What to try next

- Nothing to tune; the switch has no free parameter. If AB wants the coverage, the next step is its validation query
  (one query) followed by a roster-window decision, not further train work.
- The same tradable switch would also close E2A_D01C_FB's gap; not run, since F11 already beats D01C as a fallback.

## Do order blocks help?

Not tested here. Running answer unchanged: O01 beats O00 on 3 of 4 cells, clears the market line on none; O05 weekly
bullish +1.90 is the only encouraging cell.
