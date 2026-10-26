# E2A_D01C_FB: E2A first, D01C on the dates E2A abstains (day-bearish): diagnosis

Train split (2015-01-01 to 2020-12-31), day horizon, `top` selection. Replay:
`experiments/done/e2a-d01c-fallback-day/` (landed 62f0bb0). Card: `cards/E2A_D01C_FB.yml`. Joint test:
`reports/evidence_train.md` (day/bearish, 34 experiments).

## Pre-declared success rule: not met (one of three parts holds)

The card needed edge at least +5.74, directional move after costs at least +0.08%, and picks on at least
99% of train dates.

| Strategy | Picks | Dates (of 1,467) | Edge | t | 95% interval | Dir. move after costs | Positive years |
|---|---|---|---|---|---|---|---|
| E2A | 2,767 | 936 (64%) | +7.46 | 6.92 | +5.27 to +9.67 | +0.13% | 6/6 |
| D01C | 7,304 | 1,465 (100%) | +4.74 | 8.41 | +3.71 to +5.84 | +0.08% | 6/6 |
| **Fallback** | 4,996 | **1,386 (94%)** | **+5.97** | 7.44 | +4.37 to +7.57 | **+0.06%** | 6/6 |

Edge passes (+5.97 against +5.74). Directional move (+0.06%) and coverage (94%) fail.

Per-year edge: +2.17, +7.48, +6.28, +4.87, +6.47, +8.06 (2015-2020).

## Where it works and fails

- **D01C is weaker on exactly the dates E2A abstains.** By construction the fallback is E2A on E2A's
  dates. Backing out the rest from the totals (approximate: it assumes those dates carry E2A's own +7.46 and
  +0.13%), D01C on the remaining ~450 dates has an edge near +2.9 and a directional move near -0.03%, against
  its all-dates +4.74 and +0.08%. Both readings do best on the same kind of day (E2A fires after an extreme,
  crowded move), so the fallback hands the quiet days to D01C when D01C is at its weakest.
- **The coverage shortfall is a design gap, not a data gap.** The switch looks at E2A's raw scores, before
  the engine's universe filter. E2A scores some stock bearish on 1,015 train dates but has an in-universe
  pick on only 936; on the ~80 dates in between, the card stays with E2A, the universe filter removes those
  picks, and the table is empty. Switching on in-universe E2A picks would close it, but the strategy
  interface does not see the universe, and a fix would be a new trial.
- **Joint test:** StepM names it individually superior, and it is in the 3-strategy MCS of 34 in
  day/bearish (with E2A and D01C), so it is statistically indistinguishable from the best.

## Go-live

It meets the provisional letter on day-bearish (4,996 picks, +5.97, +0.06%), so it is eligible for one
validation query. It was not in Monday's batch, which was queued before it landed. Against its members it
trades E2A's strength for coverage: 94% of dates instead of 64%, at -1.5 points of edge. If E2A's validation
edge holds up, the fallback is the way to publish E2A without a blank table on a third of days, so its query
is worth spending. Queued in the same commit as this diagnosis (`experiments/pending/e2a-d01c-fallback-day-validation.yml`).

## What to try next

- Its validation query (queued; up to 2 more queries, so up to 24 of this week's 60 with Monday's batch).
- Not tuned further: the obvious variant (switch on in-universe picks) needs the universe inside the
  strategy, which is an engine-interface question for a supervised session, not a strategy tune.

## Do order blocks help?

Not tested here (no order-block member). Running answer unchanged: bearish leans no; bullish "not yet,
but O05's weekly-bar structure is the first candidate worth a second look".
