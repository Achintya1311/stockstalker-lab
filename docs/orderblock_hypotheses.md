# Order blocks: what we are testing and why

Source of the idea: order-block.com, a paid Indian F&O scanner, seen in a screen recording on 24 Oct 2026. It publishes
no method. Everything below is **reverse-engineered from its screenshots and is a hypothesis, not a fact.** Nothing here
is assumed to work (SPEC.md section 5); the O-series replays decide. Never copy the site's text or claims.

## What the screenshots show (verified arithmetic)

- Universe = the NSE F&O stocks (counters 213 / 28 / 20: names scanned, bullish, bearish; the rest score zero).
- Per stock: rank percentile and position (`p99.8 · #1/93`), OI state (`LONG BUILD-UP`, `SHORT BUILD-UP`), a volume delta and
  a VWAP, an order-block range (`OB lo-hi`), an entry zone `Z`, a support `S1`, resistances `R1`/`R2`, a conviction score
  (0-100, five dots), and a rule label (`PICK · BULLISH #1`).
- `RISK% = (price - zone_low) / price`, and `R:R = (R2 - zone_mid) / (zone_mid - S1)`. Both reproduce on four posted tiles
  (HCLTech, TataElxsi, Crompton, TCS) to the printed digit. R1, R2, S1 and the conviction formula are not recoverable.

## Hypothesis of the pick rule (to be ablated, not believed)

A stock is picked on a side when (1) a fresh unmitigated order block exists on that side, (2) OI build-up agrees with the side,
(3) price is at or near the zone, and (4) it ranks high on a composite of those plus volume. The lab tests each ingredient alone
and in combination so the answer to "do order blocks help?" is a number, not an opinion:

| Id | Strategy | Tests |
|----|----------|-------|
| O00 | Last opposite candle, **no impulse** requirement (placebo) | does the impulse that defines an order block matter at all |
| O01 | Order-block retest: impulse >= 1.5 ATR that breaks the 10-bar high/low | order block alone |
| D01 | OI build-up alone (already ported) | control for the OI half of the claim |
| O02 | O01 gated by D01's OI state agreeing with the side | is OB + OI better than either |
| O03 | O01 gated by trend (T01 agrees) | is OB just a trend signal in disguise |
| O04 | rank-average of O01 proximity, D01 and volume z (the "conviction" guess) | the composite as sold |
| O05 | O01 on weekly bars | horizon sensitivity (needs a weekly resample helper) |

Intraday versions (5-minute zones, session VWAP, volume delta proxies) need the archived 5-minute bars
(`intraday.yml`, 60 sessions from 29 Jul 2026). They cannot be replayed on the 2015-2020 train split, so they get
their own forward protocol: build the rule on the first 30 sessions, freeze it, score it on the rest, and compare
with the same-day base rate. Replaying them needs a workflow change under `.github/` (supervised): see
`state/engine-issues.md`.

## Rules for reading the results

- Winners-only evidence (a vendor's community screenshots) says nothing about hit rate. Only the all-stocks, all-days replay counts.
- A strategy "helps" only if O01 beats O00 and the market line out of sample, and O02 beats D01 alone.
- Public wording stays inside SPEC.md section 10: structure and rank, no entry, stop or target prices.
