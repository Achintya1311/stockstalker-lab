# CONSENSUS_DB_V1: day-bearish consensus (E2A + D01C + A09): diagnosis

Train split (2015-01-01 to 2020-12-31), day horizon, `top` selection. Replay:
`experiments/done/consensus-db-v1-day/`. Card: `cards/CONSENSUS_DB_V1.yml`. Joint test:
`reports/evidence_train.md` (day/bearish, 29 experiments).

## Pre-declared success rule: not met

The card said, before the replay: the consensus helps if its top-5 day-bearish edge beats E2A's +7.46, or
comes within 1 point of it with a directional move after costs above +0.13% and date coverage above 79%.
Edge is +4.61, about 2.9 points short, and the directional move is +0.07%. Neither branch holds. The
table's provisional choice stays with the best single member (subject to validation).

## Numbers

| Strategy | Picks | Coverage | Edge | t | Dir. move | 95% interval | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E2A | 2,767 | 79% | +7.46 | 6.92 | +0.13% | +5.27 to +9.67 | +4.17 | +8.09 | +6.77 | +5.49 | +9.26 | +10.46 |
| D01C | 7,304 | 100% | +4.74 | 8.41 | +0.08% | +3.71 to +5.84 | +2.92 | +5.07 | +6.73 | +5.99 | +2.89 | +4.66 |
| A09 | 4,710 | 90% | +3.21 | 4.01 | +0.03% | +1.64 to +4.67 | +6.53 | +4.36 | +6.61 | -1.31 | -0.70 | +4.20 |
| **Consensus** | 7,335 | 100% | **+4.61** | **8.32** | **+0.07%** | **+3.52 to +5.70** | +4.03 | +4.58 | +6.65 | +5.01 | +2.81 | +4.49 |

(Coverage is `results.json`'s, the card's own yardstick. Counted against all 1,467 train dates, as the
evidence report does, E2A has picks on 936 dates, 64%; the consensus and D01C on nearly all.)

The `all` selection (about 71 bearish-scored stocks a date) is +1.35 (t 11.20) with a directional move of
-0.08%: as with every member, the profitable part is the top of the ranking.

## Where it works and fails

- **It lands on D01C, not above it.** Edge (+4.61 vs +4.74), t (8.32 vs 8.41), interval and year pattern
  are all D01C's, with a slightly lower directional move. Approximate top-5 overlap: 43% of the consensus
  picks are D01C's, 34% A09's and 29% E2A's. Only 9% are in no member's top five, so unlike the
  week-bearish consensus it does not invent new picks. It mixes the members' picks, and the mix scores like
  the densest member.
- **E2A's strength is diluted, not added to.** E2A has picks on only 64% of train dates and is far
  stronger when it does (+7.46). Averaging its rank with two weaker, always-on readings pulls the top five toward
  them. On the days E2A abstains, neutral 0.5 hands the table to D01C and A09.
- **It does smooth A09's bad years.** A09 was negative in 2018 and 2019; the consensus is +5.01 and +2.81
  there, and positive all six years (as D01C already is).
- StepM names it individually superior, as it does E2A, D01C and A09: day-bearish is the one cell where
  the lab's evidence survives snooping (SPA p=0.000).

## Go-live

It meets the provisional rule's letter on day-bearish (7,335 picks, +4.61, +0.07%), so P1 gives it one
validation query. It is near-redundant with D01C, which beats it on directional move with the same edge,
so it is the lowest-priority query of the day-bearish batch. E2A (+7.46, +0.13%) remains the strongest
day-bearish train reading, but on its own it would leave the table blank on about 36% of days.

## What to try next

- Validation query for day-bearish (Monday batch, low priority behind E2A, D01C and A09).
- If E2A survives validation, the useful combination is a **fallback**, not an average: E2A's picks when it
  fires, D01C's on the days it abstains. That is a new pre-declared trial, not a tune of this one.
- Not worth tuning weights.

## Do order blocks help?

Not tested here (no order-block member). Running answer unchanged: bearish leans no; bullish "not yet, but
O05's weekly-bar structure is the first candidate worth a second look".
