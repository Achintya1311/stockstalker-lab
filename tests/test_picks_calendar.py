from picks.calendar import load_holidays, next_trading_session, starts_new_iso_week


def test_load_holidays_skips_blank_and_comment_lines(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("# header\n\n2026-10-20  # Dussehra\n2026-12-25\n")
    assert load_holidays(path) == {"2026-10-20", "2026-12-25"}


def test_next_trading_session_plain_weekday():
    # Monday -> Tuesday, no holiday involved.
    assert next_trading_session("2026-10-19", holidays=set()) == "2026-10-20"


def test_next_trading_session_skips_the_weekend():
    # Friday -> Monday.
    assert next_trading_session("2026-10-16", holidays=set()) == "2026-10-19"


def test_next_trading_session_skips_a_holiday():
    # 2026-10-20 (Tuesday) is Dussehra per config/nse_holidays.txt.
    assert next_trading_session("2026-10-19", holidays={"2026-10-20"}) == "2026-10-21"


def test_next_trading_session_skips_a_holiday_that_falls_on_a_monday():
    # Holiday immediately followed by the weekend already being over: a
    # Monday holiday pushes the next session to Tuesday, not back into the
    # weekend that already passed.
    assert next_trading_session("2026-01-23", holidays={"2026-01-26"}) == "2026-01-27"


def test_next_trading_session_reads_the_real_committed_holiday_file():
    # 2026-10-19 is a Monday; Tuesday 2026-10-20 is Dussehra in the real
    # config/nse_holidays.txt, so the next real trading session is Wednesday.
    assert next_trading_session("2026-10-19") == "2026-10-21"


def test_starts_new_iso_week_true_across_a_weekend():
    assert starts_new_iso_week("2026-10-16", "2026-10-19") is True


def test_starts_new_iso_week_false_within_the_same_week():
    assert starts_new_iso_week("2026-10-19", "2026-10-20") is False


def test_starts_new_iso_week_true_across_a_holiday_that_extends_the_break():
    # Friday -> the Wednesday after a Monday holiday: still a new ISO week,
    # same as an ordinary weekend rollover.
    assert starts_new_iso_week("2026-01-23", next_trading_session("2026-01-23", {"2026-01-26"})) is True
