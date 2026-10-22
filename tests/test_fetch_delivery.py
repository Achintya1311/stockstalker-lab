from pathlib import Path

from scripts import fetch_delivery


def test_url_builds_ddmmyyyy_mto_path():
    from datetime import date
    assert fetch_delivery.url(date(2015, 1, 2)) == (
        "https://nsearchives.nseindia.com/archives/equities/mto/MTO_02012015.DAT"
    )


def test_main_saves_one_file_per_trading_day(tmp_path, monkeypatch):
    requested: list[str] = []

    def fake_get(u: str) -> bytes | None:
        requested.append(u)
        return b"delivery-bytes"

    monkeypatch.setattr(fetch_delivery, "get", fake_get)
    monkeypatch.setattr(fetch_delivery.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_delivery.py",
            "--start",
            "2026-10-19",
            "--end",
            "2026-10-20",
            "--out",
            str(tmp_path),
        ],
    )

    fetch_delivery.main()

    assert (tmp_path / "delivery" / "2026" / "delivery_20261019.dat").read_bytes() == b"delivery-bytes"
    assert (tmp_path / "delivery" / "2026" / "delivery_20261020.dat").read_bytes() == b"delivery-bytes"
    assert len(requested) == 2


def test_main_records_404s_in_missing_and_skips_them_next_time(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_get(u: str) -> bytes | None:
        calls["n"] += 1
        return None

    monkeypatch.setattr(fetch_delivery, "get", fake_get)
    monkeypatch.setattr(fetch_delivery.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_delivery.py",
            "--start",
            "2026-10-18",
            "--end",
            "2026-10-18",
            "--out",
            str(tmp_path),
        ],
    )

    fetch_delivery.main()
    assert "delivery:20261018" in (tmp_path / "missing.txt").read_text().split()
    assert calls["n"] == 1

    fetch_delivery.main()  # rerun over the same range
    assert calls["n"] == 1  # the recorded miss was skipped, not re-requested


def test_main_skips_already_downloaded_files(tmp_path, monkeypatch):
    target = tmp_path / "delivery" / "2026" / "delivery_20261019.dat"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"already-here")

    def fake_get(u: str) -> bytes | None:
        raise AssertionError("should not re-fetch an existing file")

    monkeypatch.setattr(fetch_delivery, "get", fake_get)
    monkeypatch.setattr(fetch_delivery.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_delivery.py",
            "--start",
            "2026-10-19",
            "--end",
            "2026-10-19",
            "--out",
            str(tmp_path),
        ],
    )

    fetch_delivery.main()
    assert target.read_bytes() == b"already-here"
