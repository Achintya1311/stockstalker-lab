# Confluence lane: does a second condition add to the day-bearish fade family? (24 Oct 2026)

Lane question (`state/queue.md`): the lab's only signals with hit-rate edge are the day-bearish fade
family (A02, T13, T06, A09), but their directional move after costs is about zero, so hit rate alone
is not money. Does a second condition — order-block agreement, or futures OI behaviour — add real
information on top of A02, rather than just re-slicing the same picks?

Five trials were pre-registered together on 24 Oct, before any result was read (`cards/D01C.yml`,
`cards/E1A.yml`, `cards/E1B.yml`, `cards/E2A.yml`, `cards/E2B.yml`), and all five replays are now in
`experiments/done/`. Numbers below are train-split, `top` selection, day horizon only (the only horizon
these cards test). Sources: `ledger/trials.csv`, each experiment's `results.json`, and
`reports/evidence_train.md`'s stationary-bootstrap intervals / StepM superiority (the data-snooping-aware
numbers the lane's own instructions say to trust over the leaderboard t).

## Baselines

| Strategy | Side | Edge (pts) | 95% interval | Coverage | Dir. move (after costs) | StepM superior |
|---|---|---|---|---|---|---|
| a02-extreme-day-reversal-day | bearish | +4.34 | +2.62 to +6.06 | 87% | -0.044% | yes |
| a02-extreme-day-reversal-day | bullish | -1.10 | -2.97 to +0.87 | 73% | -0.625% | no |
| d01-oi-buildup-day | bearish | -2.48 | -3.54 to -1.44 | 100% | -0.154% | no |
| d01-oi-buildup-day | bullish | -4.61 | -5.75 to -3.57 | 97% | -0.748% | no |

## E1A / E1B: does an agreeing order-block zone change A02's day-bearish picks?

| Strategy | Side | Edge | Interval | Coverage | Dir. move | vs A02 base |
|---|---|---|---|---|---|---|
| e1a-day (A02 + agreeing OB zone) | bearish | +4.31 | -0.83 to +9.47 | 17% | -0.098% | -0.03 pt, interval straddles zero |
| e1b-day (A02, no/opposing OB zone — placebo) | bearish | +4.29 | +2.69 to +5.90 | 86% | -0.040% | -0.05 pt, matches A02 almost exactly |
| e1a-day | bullish | +0.59 | -5.41 to +6.28 | 15% | -0.468% | +1.69 pt but interval is 11.7 pts wide, not above 0 |
| e1b-day | bullish | -0.91 | -3.01 to +1.13 | 72% | -0.630% | +0.19 pt, noise |

**Reading:** E1B (the placebo arm, 86% coverage) reproduces A02 almost exactly on the cell that actually
has edge (day-bearish), which is itself informative — removing the minority of dates where an
order-block zone agrees barely moves A02 at all. E1A (17% coverage, 86 fewer dates than E1B pulls the
same bearish edge from a much smaller, noisier sample — its interval crosses zero, so "zone agrees" is
not shown to be better than "zone disagrees or is absent." On bullish, both arms are inside noise. **Order
blocks do not add information to A02's day-bearish fade.** Consistent with the order-block lane's own
running finding (`state/journal.md`, O00–O03): OB agreement has never cleared the market line on its own,
and layering it onto a working strategy doesn't change that.

## E2A / E2B: does futures-OI crowdedness change A02's day-bearish picks?

| Strategy | Side | Edge | Interval | Coverage | Dir. move | vs A02 base |
|---|---|---|---|---|---|---|
| e2a-day (A02, OI rose — crowded) | bearish | +7.46 | +5.27 to +9.67 | 79% | **+0.127%** | **+3.12 pt, interval entirely above 0** |
| e2b-day (A02, OI fell/flat — uncrowded) | bearish | +2.34 | +0.29 to +4.37 | 83% | -0.169% | -2.00 pt, interval above 0 but lower than base |
| e2a-day | bullish | -1.58 | -4.00 to +0.87 | 69% | -0.739% | -0.48 pt, interval straddles zero |
| e2b-day | bullish | +0.88 | -1.68 to +3.45 | 54% | -0.412% | +1.98 pt but interval straddles zero |

**Reading:** this is the lane's first real finding. Restricting A02's day-bearish fade to sessions where
near-month futures OI rose (a crowded move) clears the stop rule outright: +3.12 points over A02 alone,
StepM-superior, interval (+5.27 to +9.67) entirely above zero and not overlapping the uncrowded arm's
(+0.29 to +4.37). More importantly for the lane's whole motivation, **directional move after costs flips
from essentially zero (A02: -0.044%) to positive (+0.127%)** — the first arm in this family where hit-rate
edge and after-cost direction agree. The uncrowded arm (E2B) is worse than A02 alone on bearish, which is
the complementary half of the same result, not an independent failure: crowdedness is where A02's
day-bearish edge concentrates, and the uncrowded dates dilute it. Neither arm shows anything on bullish.
**Futures-OI crowdedness does add information to A02's day-bearish fade.**

## D01C: fading D01's OI build-up classification, on its own (not an A02 filter)

| Strategy | Side | Edge | Interval | Coverage | Dir. move | vs D01 (own base) | vs A02 |
|---|---|---|---|---|---|---|---|
| d01c-day | bearish | +4.74 | +3.71 to +5.84 | 100% | **+0.083%** | **+7.22 pt, non-overlapping** | +0.40 pt (comparable, not clearly better) |
| d01c-day | bullish | +2.54 | +1.48 to +3.60 | 100% | -0.511% | **+7.15 pt, non-overlapping** | +3.64 pt (clearly better; A02 bullish is net negative) |

**Reading:** D01C isn't a filter on A02 — it's D01's own classification with the sign flipped (per
`research/diagnostics/d01.md`'s finding that D01 lost confidently on both sides). That flip works: both
cells move from confidently negative, non-overlapping-with-zero edges to confidently positive,
non-overlapping-with-zero edges, at full coverage (D01C never abstains, since it is still D01's logic).
On bearish it lands in the same neighbourhood as A02 (not a clear beat, but a second, differently-sourced
signal reaching a similar place), and its directional move is also positive there. On bullish it clearly
beats A02, which has no real bullish edge at all. This confirms the OI-crowdedness read from E2A/E2B from
a different angle: OI behaviour, read either as a confirming filter (E2A) or as its own contrarian
classifier (D01C), is where this lane's actual edge is, not order-block zones.

## Stop rule and next step

The lane's stop rule: *"if no arm beats its base by 1 pt with an interval above 0, record it as a null in
the journal and move on."* Two arms clear it outright — **D01C** (vs its own D01 base, both sides, by
>7 points with non-overlapping intervals) and **E2A** (vs A02, bearish, by +3.12 points with an interval
entirely above zero, plus the first positive after-cost directional move in this whole family). E1A/E1B
and E2B do not. So this is not a null lane overall, and per the lane's own plan the next step is **not**
to stop, but to continue: a sigma-scaled extreme day with a GARCH forecast (`arch`), then the meta-label
stage with conformal abstention (MAPIE), both train-only — and, separately, D01C and E2A are now
candidates for the go-live track's P1 rule ("every train replay with a positive edge and positive
directional move on some table gets one validation query for that table") once holdout queries open for
the order-block/confluence work (`state/queue.md`: allowed from Mon 26 Oct, within budget). Today is
24 Oct; no query has been spent on either.

## Answer so far

**Order blocks:** no — E1A vs E1B shows no distinguishable effect of zone agreement on A02's picks,
matching the order-block lane's own standalone finding.
**Open interest:** yes, on the day-bearish fade family specifically — both as a confirming filter on A02
(E2A) and as its own contrarian classifier (D01C), OI behaviour adds real edge and is the first condition
in this family to turn the after-cost directional move positive rather than ~0. Bullish stays unhelped by
either condition.
