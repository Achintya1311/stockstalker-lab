import pandas as pd
import pytest

from scripts.check_corporate_actions import build_report, classify_ratio


@pytest.mark.parametrize("ratio,expected", [
    (0.5, "2:1 split or 1:1 bonus"),
    (1 / 3, "3:1 split or 2:1 bonus"),
    (0.2, "5:1 split"),
    (0.6321, "unrecognised ratio"),
])
def test_classify_ratio(ratio, expected):
    assert classify_ratio(ratio) == expected


def _events(rows):
    return pd.DataFrame(rows, columns=["date", "symbol", "action_ratio"])


def test_report_lists_big_jump_separately_from_all_events():
    events = _events([
        ("2020-01-03", "ABC", 0.5),
        ("2020-02-01", "XYZ", 0.95),
    ])
    report = build_report(events)
    assert "found 2 candidate event(s)" in report
    assert "## Events with an adjusted-close jump of 30% or more" in report
    big_jump_section, _, rest = report.partition("## All detected events")
    assert "ABC" in big_jump_section
    assert "XYZ" not in big_jump_section
    assert "ABC" in rest and "XYZ" in rest


def test_report_handles_no_events():
    report = build_report(_events([]))
    assert "found 0 candidate event(s)" in report
    assert "None." in report


def test_report_flags_todo_for_independent_check():
    report = build_report(_events([("2020-01-03", "ABC", 0.5)]))
    assert "TODO" in report
