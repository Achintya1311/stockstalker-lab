# NSE bhavcopy formats (headers copied from real files, 16 Oct 2026)

Never write these column names from memory; a wrong name passed every synthetic test on 16 Oct and only failed on real data.

**Old equity (to 2024-07-05)**, `cmDDMONYYYYbhav.csv`:
`SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,` (trailing comma)

**Old F&O (to 2024-07-05)**, `foDDMONYYYYbhav.csv`:
`INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,` (trailing comma). Stock futures: `INSTRUMENT == FUTSTK`.

**UDiFF equity and F&O (from 2024-07-08)**, `BhavCopy_NSE_CM|FO_0_0_0_YYYYMMDD_F_0000.csv`, 34 columns:
`TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4`

- Equity rows: `Sgmt == CM`, `FinInstrmTp == STK`, series in `SctySrs` (EQ, BE, SM, ST, GS, GB, ...). On 15 Sep 2026 there were 2,652 EQ rows.
- F&O instrument types: `STF` stock futures (629 rows on 15 Sep 2026, about 210 stocks × 3 expiries), `STO` stock options, `IDF` index futures, `IDO` index options.
- Volume is `TtlTradgVol`; turnover in rupees is `TtlTrfVal`.
