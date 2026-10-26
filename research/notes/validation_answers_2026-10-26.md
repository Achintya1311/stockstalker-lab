# Validation answers for the go-live provisional rule (26 Oct 2026)

Monday's batch (queued 32ed1dc, answered by the Replay run that committed 749239e at 04:02 UTC): 11 validation
experiments, 19 queries logged in `ledger/holdout_queries.csv` (bearish-only cards ask one side). Budget left
this ISO week: 41 of 60 after the batch, 40 of 60 after the fallback's query (`e2a-d01c-fallback-day-validation`,
answered by the Replay run that committed c59f8aa at 04:56 UTC).

## How to read a released value

`engine/holdout.py` (Thresholdout, threshold 3 points, tolerance 1 point). If the validation edge is within
about 3 points of the train edge (the cut-off itself is noised, scale 2 points), the train edge is released
unchanged and `budget_spent` is False: the validation edge is somewhere near the train edge, and nothing more
is revealed. If they disagree by more, the validation edge plus 1-point-scale noise is released and
`budget_spent` is True. So a released value equal to the train value means "validation broadly agrees", and
a different one is a noisy look at validation itself.

## Answers, by table (top-5 edge, points; eligible side only)

### Day / bearish

| Strategy | Train edge | Released | Disagreed? | Reading |
|---|---|---|---|---|
| **E2A** | +7.46 | **+6.72** | yes | validation about +6.7: holds up |
| D01C | +4.74 | +4.74 | no | validation within about 3 points of +4.74 |
| consensus_db_v1 | +4.61 | +4.61 | no | as D01C |
| A09 | +3.21 | +3.21 | no | within about 3 points |
| E2A_D01C_FB | +5.97 | +5.97 | no | within about 3 points of +5.97; below E2A's +6.72, so E2A stays |

### Week / bearish

| Strategy | Train edge | Released | Disagreed? | Reading |
|---|---|---|---|---|
| **A01 weekly reversal** | +2.48 | **+4.73** | yes | validation about +4.7, above train |
| T05C up-cross fade | +4.02 | +4.02 | no | within about 3 points of +4.02 |
| D02 contrarian | +3.75 | +3.86 | yes | validation about +3.9 |
| consensus_wb_v1 | +2.48 | +2.48 | no | within about 3 points |
| T05 down-cross | +2.02 | +2.02 | no | within about 3 points |
| A07C | +1.34 | +1.34 | no | within about 3 points |
| T15 ADX regime | +2.95 | **-0.19** | yes | **fails on validation** |

### Day / bullish and week / bullish

No eligible strategy (no positive directional move after costs), so no query was spent on them as the
provisional rule's candidates. The bullish sides that the batch also asked (both sides of each experiment
are asked) are context, not candidates: E2A day-bullish released -6.93, D01C day-bullish -1.05 (train
+2.54: **D01C's bullish side did not hold up on validation**, which matters for AB's edge-only option, since D01C
was one of its three day-bullish candidates), A09 day-bullish +0.49, the week-bullish ones near zero or negative.

## What SPEC section 10's literal rule picks today

| Table | Provisional choice | Released edge | Runner-up | Note |
|---|---|---|---|---|
| day_bearish | **E2A** | +6.72 | D01C +4.74 (released = train) | E2A has picks on 64% of train dates, so the table is empty on about a third of days; the fallback (released +5.97) would fill them but ranks below E2A |
| week_bearish | **A01 weekly reversal** | +4.73 | T05C +4.02 (released = train) | A01's train edge was modest (+2.48, interval -0.09 to +5.31 in `evidence_train.md`); validation came out higher |
| day_bullish | **champion v1** | n/a | none eligible | top-5 train edge -1.55; AB decision pending (`research/diagnostics/champion_v1.md`) |
| week_bullish | **champion v1** | n/a | none eligible | top-5 train edge -2.82; AB decision pending |

Caveats the choice should carry:
- A released value equal to train hides the validation value inside a band of about ±3 points, so T05C,
  D01C and the others are not known to be below A01 and E2A, only not shown to be above.
- The fallback's answer came back at its train value (+5.97, `budget_spent` False), below E2A's +6.72, so
  under the literal rule E2A stays and the day-bearish table is empty on about a third of days. Choosing the
  fallback for coverage instead would be a departure from "highest released edge wins": an AB call, not the
  lab's. Queued with the other two decisions.
- `config/live_source.json` is written only on Fri 30 Oct before 12:00 UTC (SPEC section 7). Until then this
  is a draft (`config/live_source.draft.json` (read by dry runs only)).
- E2A, A01 and the fallback are registered in `picks/source.py` (d158544), so a switch between them needs no
  code change.

## Same stock in both tables (found 26 Oct, unit 4)

The draft pairs champion v1 (bullish, most extended stocks) with two bearish readings that fade recent
strength. On train `top` picks, the same stock appears in both tables of one page on **69% of weeks**
(champion v1 week-bullish vs A01 week-bearish, 1.08 shared stocks a week on average) and on **23% of
E2A's days** (champion v1 day-bullish vs E2A day-bearish). `picks/` publishes each table independently, so
the public page would call one stock bullish and bearish at once. The synthetic end-to-end test
(`tests/test_picks_draft_source.py`) shows the same thing. This is a presentation decision for AB, not
something the rule settles: show both (each table is its own strategy's record), drop shared stocks from
both tables, or choose the bullish fallback differently. It is one more reason the bullish-fallback
question matters before Friday.

## Do order blocks help?

No order-block reading was eligible, so none was asked. Running answer unchanged: bearish leans no; bullish
"not yet, but O05's weekly-bar structure is the first candidate worth a second look", and no order-block
reading clears the cost test.

## 26 Oct 15:18Z: A01_I01F (week-bearish)

Released +4.17 (train value released). A01's released +4.73 stays highest, so week-bearish stays
`a01_weekly_reversal@v1`.

## 26 Oct 15:45Z: bullish batch queued (AB's edge-only decision)

Day T04, T10-NR7, T25; week T25, A05B, A04, O05, I02 (16 queries). Answers go here when they land.

## 26 Oct 18:44Z: bullish batch answered (16 queries; 37 of 60 used this week, 23 left)

| Table | Candidate | Train edge | Released edge |
|---|---|---|---|
| Day bullish | **T04 Connors RSI(2)** | +3.37 | **+4.36** |
| Day bullish | T10-NR7 | +2.16 | +2.16 |
| Day bullish | T25 Heikin-Ashi | +1.85 | +1.85 |
| Day bullish | D01C (asked earlier) | +2.54 | -1.05 |
| Day bullish | champion v1 (asked earlier) | -0.11 | +2.53 |
| Week bullish | **A05B MAX effect, ranked** | +2.23 | **+2.23** |
| Week bullish | O05 weekly order block | +1.90 | +1.90 |
| Week bullish | A04 52-week high | +1.92 | -2.49 |
| Week bullish | I02 low-vol level | +1.85 | -2.55 |
| Week bullish | T25 Heikin-Ashi | +2.74 | -7.02 |

A released value equal to the train value means validation agreed within Thresholdout's tolerance; a
different value means it did not, and the noisy validation number was released instead.

Under AB's edge-only rule for bullish tables: **day bullish T04** (+4.36, ahead of champion v1's +2.53 by
1.83 points) and **week bullish A05B** (+2.23, ahead of O05's +1.90). Both go into the draft. Both keep the
provisional label, and both still have negative directional moves after costs on train: they call direction
more often than the market line, but not by enough to pay the delivery cost. A05B repeats A05's picks
exactly (`reports/evidence_train.md`), so its record is A05's ranking under the A05B name.

Week bullish's best train reading, T25, fell to -7.02 on validation, and A04 and I02 also turned negative:
3 of 5 week-bullish candidates did not hold up out of sample.

## Do order blocks help? (bullish)

O05 held its train edge on validation (+1.90 released) and is second for week bullish, 0.33 points behind
A05B. It is the first order-block reading to hold up out of sample, but it is not the best, and its
directional move is negative.
