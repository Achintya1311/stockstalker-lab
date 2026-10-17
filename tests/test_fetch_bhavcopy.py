from datetime import date
from pathlib import Path

from scripts import fetch_bhavcopy


def test_main_attempts_weekends_not_just_weekdays(tmp_path, monkeypatch):
    """2015-02-28 (a Saturday) was a real NSE session (Union Budget special
    trading) - see state/engine-issues.md. A date loop that only tries
    weekdays never asks NSE for it at all, which is the bug this guards
    against: it must be attempted like any other day, not skipped outright.
    """
    requested: list[date] = []

    def fake_get(url: str) -> bytes | None:
        requested.append(url)
        return b"zip-bytes"

    monkeypatch.setattr(fetch_bhavcopy, "get", fake_get)
    monkeypatch.setattr(fetch_bhavcopy.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_bhavcopy.py",
            "--start",
            "2015-02-26",
            "--end",
            "2015-03-02",
            "--out",
            str(tmp_path),
        ],
    )

    fetch_bhavcopy.main()

    saturday = tmp_path / "cm" / "2015" / "cm_20150228.csv.zip"
    sunday = tmp_path / "cm" / "2015" / "cm_20150301.csv.zip"
    assert saturday.exists(), "Saturday 2015-02-28 must be attempted and saved"
    assert sunday.exists(), "Sunday 2015-03-01 must be attempted and saved"
    # every day in range (26,27,28 Feb, 1,2 Mar) x 2 segments got a request
    assert len(requested) == 5 * 2


def test_main_records_weekend_404s_in_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_bhavcopy, "get", lambda url: None)
    monkeypatch.setattr(fetch_bhavcopy.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_bhavcopy.py",
            "--start",
            "2015-02-28",
            "--end",
            "2015-02-28",
            "--out",
            str(tmp_path),
        ],
    )

    fetch_bhavcopy.main()

    missing = (tmp_path / "missing.txt").read_text().split()
    assert "cm:20150228" in missing
    assert "fo:20150228" in missing
