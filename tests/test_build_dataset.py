import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_dataset import build, merge_with_existing, parse_cm_file, parse_delivery_file, parse_fo_file

OLD_CM_CSV = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
    "RELIANCE,EQ,100.00,105.00,99.00,104.00,104.00,100.00,1000000,100000000.00,02-JAN-2015,5000,INE002A01018\n"
    "TATAMOTORS,EQ,50.00,52.00,49.00,51.00,51.50,50.50,500000,25000000.00,02-JAN-2015,2000,INE155A01022\n"
    "RELIANCE,BE,100.00,105.00,99.00,104.00,104.00,100.00,10,1000.00,02-JAN-2015,2,INE002A01018\n"
)

OLD_FO_CSV = (
    "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
    "FUTSTK,RELIANCE,29-JAN-2015,0,XX,100.00,105.00,99.00,104.00,104.00,500,50000.00,10000,100,02-JAN-2015\n"
    "FUTIDX,NIFTY,29-JAN-2015,0,XX,8000,8100,7950,8050,8050,1000,100000.00,50000,500,02-JAN-2015\n"
    "OPTSTK,TATAMOTORS,29-JAN-2015,55,CE,2.00,2.50,1.80,2.10,2.10,100,500.00,2000,20,02-JAN-2015\n"
)

UDIFF_CM_CSV = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,"
    "StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
    "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,"
    "Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2024-07-08,2024-07-08,CM,NSE,STK,1001,INE002A01018,RELIANCE,EQ,,,,,"
    "RELIANCE,200.00,205.00,199.00,204.00,204.00,200.00,,,,,600000,122400000.00,3000,,,,,,\n"
    "2024-07-08,2024-07-08,CM,NSE,STK,1002,INE062A01020,SBIN,BZ,,,,,"
    "SBIN,60.00,61.00,59.00,60.50,60.50,60.00,,,,,10000,605000.00,100,,,,,,\n"
)

UDIFF_FO_CSV = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,"
    "StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
    "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,"
    "Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2024-07-08,2024-07-08,FO,NSE,STF,2001,INE002A01018,RELIANCE,,2024-07-25,2024-07-25,,,"
    "RELIANCEFUT,200.00,205.00,199.00,204.00,204.00,,,204.00,10000,50,400,81600.00,20,,,,,,\n"
    "2024-07-08,2024-07-08,FO,NSE,IDF,2002,,NIFTY,,2024-07-25,2024-07-25,,,"
    "NIFTYFUT,24000,24100,23900,24050,24050,,,24050,20000,100,800,192400.00,40,,,,,,\n"
)


def _write_zip(tmp_path: Path, name: str, csv_text: str) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name[:-4], csv_text)  # strip trailing .zip -> inner .csv name
    return path


def test_parse_cm_old_keeps_only_eq_series(tmp_path):
    path = _write_zip(tmp_path, "cm_20150102.csv.zip", OLD_CM_CSV)
    out = parse_cm_file(path)
    assert sorted(out["symbol"]) == ["RELIANCE", "TATAMOTORS"]
    row = out[out["symbol"] == "RELIANCE"].iloc[0]
    assert row["open"] == 100.0 and row["close"] == 104.0 and row["prevclose"] == 100.0
    assert row["volume"] == 1000000 and row["date"] == "2015-01-02"


def test_parse_fo_old_keeps_only_futstk(tmp_path):
    path = _write_zip(tmp_path, "fo_20150102.csv.zip", OLD_FO_CSV)
    out = parse_fo_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]
    assert out.iloc[0]["date"] == "2015-01-02"
    assert out.iloc[0]["open_int"] == 10000.0 and out.iloc[0]["chg_in_oi"] == 100.0
    assert out.iloc[0]["expiry"] == "2015-01-29"


OLD_FO_TWO_EXPIRIES_CSV = (
    "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
    "FUTSTK,RELIANCE,29-JAN-2015,0,XX,100.00,105.00,99.00,104.00,104.00,500,50000.00,10000,100,02-JAN-2015\n"
    "FUTSTK,RELIANCE,26-FEB-2015,0,XX,101.00,106.00,98.00,105.00,105.00,80,8000.00,2000,30,02-JAN-2015\n"
    "FUTSTK,RELIANCE,26-MAR-2015,0,XX,102.00,107.00,97.00,106.00,106.00,20,2000.00,500,5,02-JAN-2015\n"
)


def test_parse_fo_old_keeps_near_month_oi_when_several_expiries_trade(tmp_path):
    path = _write_zip(tmp_path, "fo_20150102.csv.zip", OLD_FO_TWO_EXPIRIES_CSV)
    out = parse_fo_file(path)
    # three expiries for the same symbol/date collapse to one row: the soonest
    # (29-JAN), not the next (26-FEB) or far (26-MAR) month's OI.
    assert list(out["symbol"]) == ["RELIANCE"]
    assert out.iloc[0]["open_int"] == 10000.0 and out.iloc[0]["chg_in_oi"] == 100.0
    assert out.iloc[0]["expiry"] == "2015-01-29"  # the soonest, not 26-FEB/26-MAR


UDIFF_FO_TWO_EXPIRIES_CSV = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,"
    "StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
    "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,"
    "Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2024-07-08,2024-07-08,FO,NSE,STF,2001,INE002A01018,RELIANCE,,2024-07-25,2024-07-25,,,"
    "RELIANCEFUT,200.00,205.00,199.00,204.00,204.00,,,204.00,10000,50,400,81600.00,20,,,,,,\n"
    "2024-07-08,2024-07-08,FO,NSE,STF,2003,INE002A01018,RELIANCE,,2024-08-29,2024-08-29,,,"
    "RELIANCEFUT,201.00,206.00,198.00,205.00,205.00,,,205.00,2000,10,80,16400.00,30,,,,,,\n"
)


def test_parse_fo_udiff_keeps_near_month_oi_when_several_expiries_trade(tmp_path):
    path = _write_zip(tmp_path, "fo_20240708.csv.zip", UDIFF_FO_TWO_EXPIRIES_CSV)
    out = parse_fo_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]
    assert out.iloc[0]["open_int"] == 10000.0 and out.iloc[0]["chg_in_oi"] == 50.0
    assert out.iloc[0]["expiry"] == "2024-07-25"  # the soonest, not 2024-08-29


def test_parse_cm_udiff_keeps_only_eq_stk(tmp_path):
    path = _write_zip(tmp_path, "cm_20240708.csv.zip", UDIFF_CM_CSV)
    out = parse_cm_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]  # SBIN is series BZ, dropped
    row = out.iloc[0]
    assert row["close"] == 204.0 and row["prevclose"] == 200.0 and row["volume"] == 600000
    assert row["date"] == "2024-07-08"


def test_parse_fo_udiff_keeps_only_stf(tmp_path):
    path = _write_zip(tmp_path, "fo_20240708.csv.zip", UDIFF_FO_CSV)
    out = parse_fo_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]  # NIFTY is IDF (index future), dropped
    assert out.iloc[0]["open_int"] == 10000.0 and out.iloc[0]["chg_in_oi"] == 50.0
    assert out.iloc[0]["expiry"] == "2024-07-25"


def test_build_merges_cm_and_fo_with_has_future_flag(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2015" / "cm" / "2015").mkdir(parents=True)
    (raw / "2015" / "fo" / "2015").mkdir(parents=True)
    _write_zip(raw / "2015" / "cm" / "2015", "cm_20150102.csv.zip", OLD_CM_CSV)
    _write_zip(raw / "2015" / "fo" / "2015", "fo_20150102.csv.zip", OLD_FO_CSV)

    df = build(raw)
    assert set(df["symbol"]) == {"RELIANCE", "TATAMOTORS"}
    by_symbol = df.set_index("symbol")
    assert by_symbol.loc["RELIANCE", "has_future"] == True  # noqa: E712
    assert by_symbol.loc["TATAMOTORS", "has_future"] == False  # noqa: E712
    assert by_symbol.loc["RELIANCE", "oi_futstk"] == 10000.0
    assert by_symbol.loc["RELIANCE", "oi_chg_futstk"] == 100.0
    assert by_symbol.loc["RELIANCE", "expiry_futstk"] == "2015-01-29"
    assert pd.isna(by_symbol.loc["TATAMOTORS", "oi_futstk"])  # no future, no OI
    assert pd.isna(by_symbol.loc["TATAMOTORS", "expiry_futstk"])  # no future, no expiry


def test_build_finds_files_regardless_of_directory_nesting(tmp_path):
    raw = tmp_path / "raw"
    (raw / "recent" / "cm" / "2024").mkdir(parents=True)
    _write_zip(raw / "recent" / "cm" / "2024", "cm_20240708.csv.zip", UDIFF_CM_CSV)

    df = build(raw)
    assert list(df["symbol"]) == ["RELIANCE"]


def test_merge_with_existing_updates_overlapping_rows_and_keeps_the_rest():
    existing = pd.DataFrame([
        {"date": "2015-01-02", "symbol": "RELIANCE", "close": 104.0, "has_future": True},
        {"date": "2015-01-05", "symbol": "RELIANCE", "close": 110.0, "has_future": True},
    ])
    fresh = pd.DataFrame([
        {"date": "2015-01-02", "symbol": "RELIANCE", "close": 999.0, "has_future": True},
        {"date": "2015-01-06", "symbol": "RELIANCE", "close": 111.0, "has_future": False},
    ])
    out = merge_with_existing(existing, fresh)
    out = out.set_index("date")
    assert out.loc["2015-01-02", "close"] == 999.0  # overwritten by fresh
    assert out.loc["2015-01-05", "close"] == 110.0   # kept from existing
    assert out.loc["2015-01-06", "close"] == 111.0   # added from fresh


def test_parse_cm_file_rejects_unrecognised_columns(tmp_path):
    path = _write_zip(tmp_path, "cm_20150102.csv.zip", "A,B,C\n1,2,3\n")
    with pytest.raises(ValueError):
        parse_cm_file(path)


OLD_DELIVERY_DAT = (
    "Security Wise Delivery Position - Compulsory Rolling Settlement\n"
    "10,MTO,02012015,325859130,0001536\n"
    "Trade Date <02-JAN-2015>,Settlement Type <N>,Settlement No <2015002>,Settlement Date <06-JAN-2015>\n"
    "Record Type,Sr No,Name of Security,Quantity Traded,Deliverable Quantity(gross across client level),"
    "% of Deliverable Quantity to Traded Quantity\n"
    "20,1,RELIANCE,EQ,76443,50983,66.69\n"
    "20,2,TATAMOTORS,BE,3463989,1431340,41.32\n"
)

RECENT_DELIVERY_DAT = (
    "Security Wise Delivery Position - Compulsory Rolling Settlement\n"
    "10,MTO,19102026,1725126165,0003405\n"
    "Trade Date <19-OCT-2026>,Settlement Type <N>\n"
    "Record Type,Sr No,Name of Security,Quantity Traded,Deliverable Quantity(gross across client level),"
    "% of Deliverable Quantity to Traded Quantity\n"
    "20,1,RELIANCE,EQ,3480001,2208053,63.45\n"
)


def test_parse_delivery_old_era_preamble_keeps_only_eq_series(tmp_path):
    path = tmp_path / "delivery_20150102.dat"
    path.write_text(OLD_DELIVERY_DAT)
    out = parse_delivery_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]  # TATAMOTORS is series BE, dropped
    row = out.iloc[0]
    assert row["date"] == "2015-01-02"
    assert row["deliv_qty"] == 50983.0
    assert row["deliv_pct"] == 66.69


def test_parse_delivery_recent_era_shorter_preamble(tmp_path):
    path = tmp_path / "delivery_20261019.dat"
    path.write_text(RECENT_DELIVERY_DAT)
    out = parse_delivery_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]
    assert out.iloc[0]["date"] == "2026-10-19"
    assert out.iloc[0]["deliv_qty"] == 2208053.0
    assert out.iloc[0]["deliv_pct"] == 63.45


def test_parse_delivery_rejects_unrecognised_filename(tmp_path):
    path = tmp_path / "not_a_delivery_file.dat"
    path.write_text(OLD_DELIVERY_DAT)
    with pytest.raises(ValueError):
        parse_delivery_file(path)


def test_build_merges_delivery_columns_by_date_and_symbol(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2015" / "cm" / "2015").mkdir(parents=True)
    (raw / "2015" / "delivery" / "2015").mkdir(parents=True)
    _write_zip(raw / "2015" / "cm" / "2015", "cm_20150102.csv.zip", OLD_CM_CSV)
    (raw / "2015" / "delivery" / "2015" / "delivery_20150102.dat").write_text(OLD_DELIVERY_DAT)

    df = build(raw)
    by_symbol = df.set_index("symbol")
    assert by_symbol.loc["RELIANCE", "deliv_qty"] == 50983.0
    assert by_symbol.loc["RELIANCE", "deliv_pct"] == 66.69
    # TATAMOTORS has a price row but no matching EQ delivery row that date
    assert pd.isna(by_symbol.loc["TATAMOTORS", "deliv_qty"])


def test_build_without_any_delivery_files_leaves_columns_all_nan(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2015" / "cm" / "2015").mkdir(parents=True)
    _write_zip(raw / "2015" / "cm" / "2015", "cm_20150102.csv.zip", OLD_CM_CSV)

    df = build(raw)
    assert df["deliv_qty"].isna().all()  # column present (joined schema), no delivery files fetched yet


def test_manifest_reports_trading_days_and_largest_gap(tmp_path):
    from scripts.build_dataset import write_manifest
    import json
    df = pd.DataFrame({"date": ["2015-01-01", "2015-01-02", "2015-01-12"], "symbol": ["A", "A", "A"]})
    write_manifest(df, tmp_path / "none.parquet", tmp_path / "m.json")
    m = json.loads((tmp_path / "m.json").read_text())
    assert m["trading_days"] == 3 and m["max_gap_days"] == 10
