import pandas as pd

from scripts.fetch_intraday import load_symbols, manifest, merge


def _bars(sym, closes):
    ts = pd.date_range("2026-10-05 09:15", periods=len(closes), freq="5min")
    return pd.DataFrame({"symbol": sym, "ts": ts, "open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0})


def test_merge_keeps_union_and_prefers_newer_bar():
    old = _bars("AAA", [1.0, 2.0, 3.0])
    new = _bars("AAA", [9.0, 9.0, 9.0, 4.0])  # overlaps 3 bars, adds one
    out = merge(old, new)
    assert len(out) == 4 and out["close"].tolist() == [9.0, 9.0, 9.0, 4.0]


def test_merge_into_empty_store_and_manifest_counts():
    out = merge(pd.DataFrame(), pd.concat([_bars("AAA", [1.0, 2.0]), _bars("BBB", [3.0])]))
    m = manifest(out, ["CCC"])
    assert (m["rows"], m["symbols"], m["sessions"], m["failed_last_run"]) == (3, 2, 1, ["CCC"])


def test_universe_file_has_the_f_and_o_stocks_and_no_indices():
    syms = load_symbols()
    assert 200 <= len(syms) <= 230 and "RELIANCE" in syms and "NIFTY" not in syms
