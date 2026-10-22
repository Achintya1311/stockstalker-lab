# NSE bhavcopy formats (headers copied from real files, 16 Oct 2026)

Never write these column names from memory; a wrong name passed every synthetic test on 16 Oct and only failed on real data.

**Old equity (to 2024-07-05)**, `cmDDMONYYYYbhav.csv`:
`SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,` (trailing comma)

**Old F&O (to 2024-07-05)**, `foDDMONYYYYbhav.csv`:
`INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,` (trailing comma). Stock futures: `INSTRUMENT == FUTSTK`. Confirmed directly against a real file (`fo02JAN2015bhav.csv`, fetched 22 Oct): distinct `INSTRUMENT` values are `FUTIDX, FUTIVX, FUTSTK, OPTIDX, OPTSTK`. Stock options: `INSTRUMENT == OPTSTK`, `OPTION_TYP` in `{CE, PE}` (24,368 `OPTSTK` rows on 02-Jan-2015), `STRIKE_PR` and `OPEN_INT` populated per strike (D02's stock-level put/call OI need).

**UDiFF equity and F&O (from 2024-07-08)**, `BhavCopy_NSE_CM|FO_0_0_0_YYYYMMDD_F_0000.csv`, 34 columns:
`TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4`

- Equity rows: `Sgmt == CM`, `FinInstrmTp == STK`, series in `SctySrs` (EQ, BE, SM, ST, GS, GB, ...). On 15 Sep 2026 there were 2,652 EQ rows.
- F&O instrument types: `STF` stock futures (629 rows on 15 Sep 2026, about 210 stocks × 3 expiries), `STO` stock options, `IDF` index futures, `IDO` index options. Confirmed directly against a real file (`BhavCopy_NSE_FO_0_0_0_20260915_F_0000.csv`, fetched 22 Oct): `STO` rows carry `StrkPric`, `OptnTp` in `{CE, PE}`, and the same `OpnIntrst`/`ChngInOpnIntrst` pair as `STF` rows, per strike (D02's stock-level put/call OI need).
- Volume is `TtlTradgVol`; turnover in rupees is `TtlTrfVal`.

**Security-wise delivery position (MTO), one era since at least 2015**, `https://nsearchives.nseindia.com/archives/equities/mto/MTO_DDMMYYYY.DAT` (plain text, not zipped; D02/D03 in `cards/catalog.csv`). Confirmed against real files dated 2015-01-02, 2015-06-15, 2024-07-08/09, 2026-09-15 and 2026-10-19 — same shape the whole span, no old/UDiFF split:

```
Security Wise Delivery Position - Compulsory Rolling Settlement
10,MTO,02012015,325859130,0001536
Trade Date <02-JAN-2015>,Settlement Type <N>,Settlement No <2015002>,Settlement Date <06-JAN-2015>
Record Type,Sr No,Name of Security,Quantity Traded,Deliverable Quantity(gross across client level),% of Deliverable Quantity to Traded Quantity
20,1,20MICRONS,EQ,76443,50983,66.69
```

Only `20,...` rows carry data: `RecordType,SrNo,SYMBOL,SERIES,QtyTraded,DeliverableQty,DeliveryPct` (7 fields, always numeric — no `-` placeholders seen). The three header lines above it vary slightly by era (the `Trade Date <...>` line sometimes carries a trailing `,Settlement No <...>,Settlement Date <...>` and sometimes doesn't) so a parser should skip to the first `20,` line rather than assume a fixed header length. No trailer line. Restrict to `SERIES == "EQ"` same as the main bhavcopy.
