# O04 ablations: O04A (without volume) and O04B (without D01): diagnosis

Train split (2015-01-01 to 2020-12-31), `top` selection. Replays: `experiments/done/o04a-no-volume-{day,week}/`
and `.../o04b-no-d01-{day,week}/` (landed 62f0bb0). Cards: `cards/O04A.yml`, `cards/O04B.yml`. Base:
`research/diagnostics/o04.md`. Joint test: `reports/evidence_train.md`.

Question: O04 (rank-average of O01 proximity, D01 OI build-up and A07 volume z, signed by the order block's
side) lost to O01 alone on all four cells. Which ingredient did that?

## Numbers (top-5 edge, points; same picks and dates in every column, since all four abstain with O01)

| Cell | O01 alone | O04 (all three) | O04A (no volume) | O04B (no D01) |
|---|---|---|---|---|
| Day bullish | -0.47 | -1.16 | -1.08 | **+0.23** |
| Day bearish | +0.66 | -0.65 | -0.37 | +0.33 |
| Week bullish | -2.21 | -2.95 | -2.88 (interval -5.22 to -0.59) | -1.68 |
| Week bearish | +0.18 | -0.44 | -0.03 | -1.12 |

Directional move after costs is negative in every cell of every variant (O04B day bullish -0.58%, the best
bullish cell, is still below the 0.415% delivery cost). No interval excludes zero on the positive side.

## Pre-declared rule, per card

- **Volume named as O04's problem if O04A beats O04 by at least 1 point in a cell:** no cell (gains
  +0.08, +0.28, +0.07, +0.41). Dropping the volume z changes almost nothing, as A07C's diagnosis expected.
- **D01 named as O04's problem if O04B beats O04 by at least 1 point in a cell:** **day bullish (+1.39)
  and week bullish (+1.27)**; day bearish just misses (+0.98); week bearish goes the other way (-0.68).
- **The composite helps only if an ablation beats O01 alone by at least 1 point with a positive directional
  move:** no cell. O04B's best margins over O01 are +0.70 (day bullish) and +0.53 (week bullish), with
  negative directional moves.

Both cards' written expectations held: O04A did no better than O04, and O04B beat O04 on the day cells
(clearly on bullish, narrowly short on bearish) without beating O01.

## Reading

- **D01 is what sank O04's bullish cells.** Aligning D01's OI build-up with the zone's side and ranking on
  it pushes up exactly the stocks where D01 is confidently wrong (`d01.md`: D01 bullish -4.61). Removing it
  recovers most of the loss.
- **But nothing in the composite adds information to O01.** With D01 gone, the volume z is close to noise,
  so O04B is O01 re-ranked by noise: within about a point of O01 in every cell, sometimes above, sometimes
  below. The "conviction score" idea, in the lab's reading of it, does not help.
- O04B week bearish (-1.12) is worse than O01 (+0.18): there the volume ingredient pulls in the wrong
  direction, consistent with A07's own week-bearish loss.

## Go-live

None eligible: no positive directional move after costs in any cell.

## What to try next

- Close the O04 composite family. A D01C-aligned composite (the faded OI reading) would be a new hypothesis,
  not an ablation, and would mostly re-test D01C, which already exists.
- The order-block lane's live lead stays O05 (weekly-bar zones), whose week-bullish edge (+1.90) is the
  lane's only positive bullish cell, also without a positive directional move.

## Do order blocks help?

Not through a composite: removing D01 explains O04's extra loss, but neither ablation beats the bare order
block (O01) by a point anywhere. Running answer: bearish leans no; bullish "not yet, but O05's weekly-bar
structure is the first candidate worth a second look", and no order-block reading clears the cost test.
