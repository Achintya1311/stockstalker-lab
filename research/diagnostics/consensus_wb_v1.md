# CONSENSUS_WB_V1: week-bearish consensus (D02-contrarian + A01 + T15): diagnosis

Train split (2015-01-01 to 2020-12-31), week horizon, `top` selection. Replay:
`experiments/done/consensus-wb-v1-week/`. Card: `cards/CONSENSUS_WB_V1.yml`. Joint test:
`reports/evidence_train.md` (week/bearish, 26 experiments).

## Pre-declared success rule: not met

The card said, before the replay: the consensus helps if its top-5 week-bearish edge beats D02-contrarian's
+3.75, or matches it with a directional move after costs above +0.16%, on more picks per date. It does
neither: edge +2.48 (below +3.75) and directional move +0.15% (just below +0.16%). So by its own rule, the
three weak signals did not add up to more than the best one.

## Numbers

| Strategy | Picks | Dates | Coverage | Edge | t | Dir. move | 95% interval | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D02-contrarian | 661 | 225 | 73% | +3.75 | 1.68 | +0.16% | -0.64 to +8.36 | -1.38 | -2.14 | +5.95 | +3.52 | +10.22 | +5.52 |
| A01 | 1,538 | 309 | 100% | +2.48 | 1.83 | +0.02% | -0.09 to +5.31 | +2.15 | +5.91 | +2.36 | -1.55 | +1.99 | +4.10 |
| T15 | 1,456 | 299 | 99% | +2.95 | 2.20 | +0.02% | +0.30 to +5.62 | +5.21 | -1.08 | +3.61 | +2.98 | +1.87 | +5.80 |
| **Consensus** | 1,545 | 309 | 100% | **+2.48** | **2.06** | **+0.15%** | **+0.17 to +4.84** | +1.73 | +8.22 | -2.64 | +3.73 | +3.92 | -0.13 |

The `all` selection (every bearish-scored stock, about 71 a date) is +0.45 (t 1.66) with a directional move
of -0.05%: the edge sits in the top of the ranking, not in the broad field.

## Where it works and fails

- **It is mostly A01 and T15, not D02.** Approximate daily top-5 overlap (from the pick logs, before the
  in-universe filter): 11% of the consensus picks are also D02-contrarian's, 28% are A01's and 35% are
  T15's. D02 reads only the 2 or 3 stocks a week with an extreme PCR; A01 and T15 read nearly every stock.
  A stock ranked high by both A01 and T15 scores (0.99 + 0.99 + 0.5) / 3 = 0.83, about what D02's single
  strongest stock gets, so the dense members crowd out D02's rare but stronger reading. Treating abstention
  as neutral (0.5), fixed before the replay, is what dilutes it.
- **It picks stocks that no member ranks first.** 38% of the consensus picks (592 of 1,560, same
  approximation) are in no member's own top five. That is the point of rank-averaging, but here it cost
  accuracy in 2017, when all three
  members were positive (+5.95, +2.36, +3.61) and the consensus was -2.64. 2020 is also flat (-0.13)
  against members at +4.1 to +5.8.
- **What it gains is steadiness and profitability.** It has a full table every week (D02 is empty or
  part-empty on 27% of weeks), its bootstrap interval is above zero (+0.17 to +4.84; D02's and A01's both
  straddle zero), and its directional move after costs (+0.15%) is close to D02's and well above A01's and
  T15's (+0.02%). Of the week-bearish readings with an interval above zero (T01, T15, the consensus), it is
  the only one whose directional move is clearly positive.
- 4 of 6 years positive. The joint test still clears nothing for week-bearish (SPA p=0.198, StepM empty).

## Go-live

It meets SPEC.md section 10's provisional rule on week-bearish (1,545 train picks, edge +2.48, directional
move +0.15%), so P1 gives it one validation query alongside D02-contrarian, A01 and T15. Its own
pre-declared rule failed, so it is not "better than D02". It is a different trade-off: lower point edge, a
full table every week and a tighter interval. The provisional rule picks on released validation edge, so
the holdout decides.

## What to try next

- Validation query for week-bearish (in the Monday batch, within `gates/budgets.py`).
- A different combination rule is a **new trial, not a tune**: skip abstainers rather than treat them as
  neutral (O04's rule), or use D02 as a gate (rank by A01+T15 only among stocks D02 also flags). The second
  gives at most D02's coverage, so it trades away the full table.
- Not worth tuning weights: three members and six years give nothing stable to tune on.

## Do order blocks help?

Not tested here (no order-block member). Running answer unchanged: bearish leans no; bullish "not yet, but
O05's weekly-bar structure is the first candidate worth a second look".
