# Champion v1 (current StockStalker blend): `top` selection diagnosis

Train split (2015-01-01 to 2020-12-31), `top` selection (the 5 picks a table publishes each date). Replays:
`experiments/done/champion-v1-day/` and `.../champion-v1-week/`. Whole-universe baseline:
`reports/champion_v1_train.md`. Joint test: `reports/evidence_train.md`.

## Why this matters now

SPEC.md section 10: a table with no provisional candidate falls back to champion v1. No bullish reading in
the lab meets the provisional letter on either horizon (`research/notes/provisional_candidates.md`), so
**both bullish tables would go live on champion v1**. Until these two replays, its `top` numbers were not
known. They are below.

## Numbers

| Horizon | Side | Picks | Coverage | Edge | t | 95% interval | P(edge<=0) | Positive years | Dir. move after costs |
|---|---|---|---|---|---|---|---|---|---|
| Day | Bullish | 7,137 | 98% | **-1.55** | -2.51 | -2.73 to -0.36 | 0.996 | 1/6 | -0.61% |
| Day | Bearish | 7,171 | 98% | +1.37 | 2.37 | +0.26 to +2.50 | 0.009 | 6/6 | -0.05% |
| Week | Bullish | 1,508 | 98% | **-2.82** | -2.06 | -5.51 to -0.36 | 0.991 | 1/6 | -0.78% |
| Week | Bearish | 1,515 | 98% | +0.41 | 0.33 | -1.91 to +2.70 | 0.359 | 3/6 | -0.01% |

Per-year edge, day bullish: +0.40, -3.28, -2.33, -1.45, -0.43, -1.81. Week bullish: +0.67, -3.82, -3.65,
-5.11, -0.56, -3.76 (2015-2020). Both are negative every year from 2016.

The whole-universe (`all`) readings in `reports/champion_v1_train.md` are near zero (day bullish -0.10,
week bullish +0.12). So the blend's ranking is the problem: **its five highest bullish scores do worse than
its average bullish score**, on both horizons. That fits the lab's other trend and momentum results
(T05, T08, T09 bullish all negative at the top): stocks that have just rallied hardest tend to lag over the
next day or week. The blend is 40% trend and 35% momentum, so its top bullish five are those stocks.

## The bullish tables cannot leave champion v1 under the current rule

The binding test is the directional move after costs, not the edge. A bullish pick is costed as a delivery
round trip (`engine/scoring.py`: 0.2% STT + 0.015% stamp + 0.2% slippage = **0.415%**). A bearish pick is
costed as a futures trade (**0.25%**). Across every train experiment with at least 500 bullish `top` picks:

- the best day-bullish directional move is -0.41% (E2B), so no day reading earns its 0.415% cost;
- the best week-bullish directional move is -0.28% (D02-contrarian);
- several bullish readings have a positive edge, and on day bullish StepM names three as individually
  superior (D01C +2.54, T04 +3.37, T10-NR7 +2.16; SPA p=0.003). All of them are
  excluded by the directional-move test alone.

So, as the rule stands, the strongest day-bullish evidence in the lab is set aside and the table falls back
to a strategy whose train edge is significantly negative. This is not a tuning question the lab can fix:
SPEC.md is protected, and the cost model is in `engine/`. **It is a decision for AB** (queued in
`state/queue.md`). Options the lab can see, without recommending a wording change it cannot make:

1. Keep the rule. Bullish tables go live on champion v1 with a known negative train edge.
2. Let the bullish tables apply the rule with the edge and pick-count tests only, if AB judges the delivery
   cost model too strict for a one-day open-to-close reading (the day table is not a delivery holding).
3. Publish no bullish table until a candidate meets the full letter.

Whatever AB decides, the validation batch already staged spends no queries on bullish readings, because
none were eligible. Option 2 would add D01C, T04 and T10-NR7 day-bullish queries to the batch.

## Bearish sides (for completeness)

Champion v1 bearish is mildly positive on day (+1.37, positive all six years) but far below E2A (+7.46) and
D01C (+4.74), and its directional move after costs is negative, so it does not meet the provisional letter
either. Both bearish tables have eligible candidates and do not fall back to it.

## What to try next

- AB decision on the bullish fallback (above). Needed before `config/live_source.json`, due Fri 30 Oct
  12:00 UTC.
- A pre-declared **champion v1 flipped at the top** card (top-5 bullish scores called bearish) is the
  same idea as T05C and D01C. Low priority: champion's bearish side already exists and T05C tests the
  cleaner version of the hypothesis.

## Do order blocks help?

Not tested here (champion v1 has no order-block ingredient). Running answer unchanged: bearish leans no;
bullish "not yet, but O05's weekly-bar structure is the first candidate worth a second look", with the
new caveat that O05 week bullish (-0.40% after costs) also fails the directional-move test.
