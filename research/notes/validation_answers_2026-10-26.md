# Validation answers for the go-live provisional rule (26 Oct 2026)

Monday's batch (queued 32ed1dc, answered by the Replay run that committed 749239e at 04:02 UTC): 11 validation
experiments, 19 queries logged in `ledger/holdout_queries.csv` (bearish-only cards ask one side). Budget left
this ISO week: 41 of 60 before the fallback's query (`e2a-d01c-fallback-day-validation`, still pending).

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
| E2A_D01C_FB | +5.97 | pending | | query queued 62758e4 |

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
| day_bearish | **E2A** | +6.72 | D01C +4.74 (released = train) | E2A has picks on 64% of train dates, so the table is empty on about a third of days; the fallback's answer is still to come |
| week_bearish | **A01 weekly reversal** | +4.73 | T05C +4.02 (released = train) | A01's train edge was modest (+2.48, interval -0.09 to +5.31 in `evidence_train.md`); validation came out higher |
| day_bullish | **champion v1** | n/a | none eligible | top-5 train edge -1.55; AB decision pending (`research/diagnostics/champion_v1.md`) |
| week_bullish | **champion v1** | n/a | none eligible | top-5 train edge -2.82; AB decision pending |

Caveats the choice should carry:
- A released value equal to train hides the validation value inside a band of about ±3 points, so T05C,
  D01C and the others are not known to be below A01 and E2A, only not shown to be above.
- The fallback's answer (pending) could replace E2A only if its released edge is higher; with train +5.97 that
  needs validation to beat train by 3 or more points.
- `config/live_source.json` is written only on Fri 30 Oct before 12:00 UTC (SPEC section 7). Until then this
  is a draft (`config/live_source.draft.json` (read by dry runs only)).
- `picks/source.py`'s registry only knows champion v1, so E2A and A01 must be registered before Friday, or
  the first live run would fail on an unknown strategy id.

## Do order blocks help?

No order-block reading was eligible, so none was asked. Running answer unchanged: bearish leans no; bullish
"not yet, but O05's weekly-bar structure is the first candidate worth a second look", and no order-block
reading clears the cost test.
