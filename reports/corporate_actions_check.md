# Corporate actions check

`detect_corporate_actions` found 3 candidate event(s) in the full dataset. Each is a (date, symbol) where PREVCLOSE departed from the prior day's CLOSE by more than the rounding-noise tolerance.

**This count collapsed from 19,825 (first run) to 3 across two root-cause fixes this session** (missing weekend special sessions, then EQ/BE series gaps — see `state/journal.md` and `state/engine-issues.md`). The acceptance note below asking for 10+ cross-checks assumed the detector would keep finding real splits and bonuses once the noise was cleaned up; **it does not** — see the "detector cannot find what B3 is for" entry in `state/engine-issues.md`, flagged for a supervised session. Real NSE splits and bonuses (HDFCBANK 1:2 split, 19 Sep 2019; WIPRO 1:3 bonus, 6 Mar 2019 — both checked directly against the raw bhavcopy) leave PREVCLOSE **unchanged** from the prior day's literal CLOSE; the share-count change shows up only in that day's own trading, which this detector cannot distinguish from an ordinary large move. Below are the only 3 candidates left, all cross-checked; none is a split or bonus.

## Independent-source cross-check

Only 3 candidates exist (see note above on why 10+ is no longer reachable with this detector). All 3 are checked:

| Date | Symbol | Ratio | Finding | Source |
|---|---|---|---|---|
| 2022-01-06 | SETFGOLD | 0.0101 | **Confirmed, but not a split/bonus**: NSE face-value sub-division of SBI-ETF Gold from ₹100 to ₹1 (loosely called "1:100" by aggregators, but units held were unchanged), ex-date 6 Jan 2022, new ISIN INF200KA16D8 from the same date. Matches our ratio (~1/100) and date exactly. | NSE circular ref. the F&O early-pay-in notice (ex-date 06-JAN-2022, record date 07-JAN-2022); corroborated by MSE Circular 11316 |
| 2018-09-18 | CARERATING | 0.9716 | **Plausible, not confirmed**: aggregator dividend tables (Parqet) list a CARE Ratings payout tied to 18-Sep-2018, consistent with a ~2.8% NSE dividend base-price adjustment, but no primary NSE/BSE filing was found to confirm the exact ex-date or amount. Treated as unconfirmed. | Parqet dividend history (secondary source only) |
| 2018-09-18 | CUPID | 0.9888 | **Unexplained**: no dividend, bonus or split with an ex-date of 18-Sep-2018 found for CUPID (its 2018 corporate actions found were a ₹1 interim dividend ex-dated 19-Nov-2018 and a 1:5 bonus around Oct/Nov 2018 — different dates, and neither ratio matches 0.9888 anyway). Left open; may be a small, unlisted-by-aggregators dividend adjustment or a genuine data anomaly. | TipRanks + 5paisa dividend tables (neither covers this date) |

## Events with an adjusted-close jump of 30% or more

| Date | Symbol | Ratio | Likely action | Checked against independent source |
|---|---|---|---|---|
| 2022-01-06 | SETFGOLD | 0.0101 | unrecognised ratio | Confirmed — NSE face-value split 100→1, not a unit split; see table above |

## All detected events

| Date | Symbol | Ratio | Likely action |
|---|---|---|---|
| 2018-09-18 | CARERATING | 0.9716 | unrecognised ratio |
| 2018-09-18 | CUPID | 0.9888 | unrecognised ratio |
| 2022-01-06 | SETFGOLD | 0.0101 | unrecognised ratio |
