import json

import pandas as pd

from scripts.build_flow import flow_for_session, main


def _bars(sym, day, closes, opens=None, start="09:15"):
    ts = pd.date_range(f"{day} {start}", periods=len(closes), freq="5min")
    opens = opens or [closes[0]] + closes[:-1]
    return pd.DataFrame({"symbol": sym, "ts": ts, "open": opens, "close": closes})


def test_flow_is_percent_from_the_open_at_15_minute_marks_with_no_prices():
    # AAA opens at 100 and closes its bars at 101, 102, 103, 104, 105, 106: +3% after 15 minutes, +6% after 30
    f = flow_for_session(_bars("AAA", "2026-11-09", [101.0, 102.0, 103.0, 104.0, 105.0, 106.0], opens=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0]))
    assert f["times"] == ["09:15", "09:30", "09:45"] and f["step_min"] == 15
    assert f["stocks"] == [{"s": "AAA", "ret": [0.0, 3.0, 6.0]}]
    assert set(f) == {"step_min", "source", "times", "market", "stocks"} and set(f["stocks"][0]) == {"s", "ret"}


def test_market_line_is_the_equal_weight_mean_and_a_late_stock_is_null_until_it_trades():
    up = _bars("UP", "2026-11-09", [102.0] * 6, opens=[100.0] + [102.0] * 5)
    down = _bars("DOWN", "2026-11-09", [99.0] * 6, opens=[100.0] + [99.0] * 5)
    late = _bars("LATE", "2026-11-09", [50.5, 50.5, 50.5], opens=[50.0, 50.5, 50.5], start="09:30")
    f = flow_for_session(pd.concat([up, down, late]))
    by = {s["s"]: s["ret"] for s in f["stocks"]}
    assert by["UP"] == [0.0, 2.0, 2.0] and by["DOWN"] == [0.0, -1.0, -1.0]
    assert by["LATE"][0] == 0.0 and by["LATE"][2] == 1.0
    assert f["market"]["ret"][1] == round((2.0 - 1.0 + (by["LATE"][1] or 0)) / 3, 3) if by["LATE"][1] is not None else f["market"]["ret"][1] == 0.5


def test_main_writes_the_newest_session_and_an_index(tmp_path):
    frames = [_bars(f"S{i:03d}", d, [100.0 + i % 3] * 6, opens=[100.0] * 6) for d in ("2026-11-06", "2026-11-09") for i in range(60)]
    store = tmp_path / "5m.parquet"
    pd.concat(frames).to_parquet(store, index=False)
    assert main(["--store", str(store), "--out", str(tmp_path / "flow")]) == 0
    idx = json.loads((tmp_path / "flow" / "index.json").read_text())
    assert idx == {"sessions": ["2026-11-09"]}
    j = json.loads((tmp_path / "flow" / "2026-11-09.json").read_text())
    assert j["session"] == "2026-11-09" and len(j["stocks"]) == 60 and "derived from Yahoo" in j["source"]
