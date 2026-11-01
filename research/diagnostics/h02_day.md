# H02 day horizon: idiosyncratic volatility, diagnosis

Train split, day horizon, `top` selection. Replay: `experiments/done/h02-idiosyncratic-volatility-day/`. Card: `cards/H02.yml`
(same code as the week test; one more trial, pre-declared 30 Oct). Week result: `research/diagnostics/h02.md`.

## Numbers

| Side | Picks | Edge | t | 95% interval | Positive years | Dir. move after costs |
|---|---|---|---|---|---|---|
| Bullish (lowest idio vol) | 7,325 | +1.18 | +2.10 | +0.09 to +2.25 | 5/6 | -0.47% |
| Bearish (highest idio vol) | 7,325 | +2.06 | +3.67 | +0.99 to +3.09 | 5/6 | +0.06% |

Bearish per year (2015-2020): +3.51, -0.44, +1.01, +2.00, +3.95, +2.43. Bullish: +1.79, +0.69, +0.57, +2.99, -0.59, +1.68.
Coverage 100% of 1,465 dates. Bearish is not StepM superior at day (the day-bearish superior set is the A02/E2A reversal
family); the week-bearish reading remains the only one named there.

## Pre-declared rule (card, 30 Oct)

Predicted day bearish +1.0 to +3.5 with a **negative** directional move; bullish -1.0 to +1.5, negative directional move.
Edges **held** (bearish +2.06, bullish +1.18). The bearish directional move is **slightly positive (+0.06%)**, against
the prediction, so the gross one-day move is about +0.31%, above the 0.25% futures cost, not "well under" it as guessed.
- Helps, day bearish (full SPEC 10 rule: +2.0, interval above 0, 4 of 6 years, positive directional move): **met**
  (+2.06 is only just over the bar; 2016 is the miss).
- Query: bar was a train edge of +7.72 (to replace E2A's released +6.72). +2.06 is far below, so **no query is spent**.

## Where it works and fails

- Same sign and similar strength across horizons (day +2.06, week +3.84): a stable, slow-moving property of the stock,
  not a one-day trigger. It is on 83% of dates a different set of names from the reversal family: top-5 bearish overlap
  1.8% with E2A (over its 1,216 firing dates) and 2.6% with A02.
- Weakest in 2016 (-0.44), strongest 2015 and 2019, as at week.
- Bullish (calm names) is a small positive that the 0.415% delivery cost wipes out (dir -0.47%).
- Positive directional move on a one-day bearish table is rare in this lab (only T04/T06/T13-type readings come within
  0.03%); H02 clears it by a hair, so it is fragile to the cost assumption.

## What to try next

- A confluence, not a replacement: H02-high-ivol AND A02 extreme-up-day (does the fade harden on volatile names?). Pre-declare before queuing.
- Do not rank-average with E2A (past consensus readings landed below their strongest member).
- Day-bearish H02 is a candidate member for the P2 consensus, as an independent family (1.8% overlap).

## Do order blocks help?

Not tested here. Running answer unchanged: O01 beats O00 on 3 of 4 cells but clears the market line on none; O05 weekly bullish (+1.90) is the lane's only encouraging cell.
