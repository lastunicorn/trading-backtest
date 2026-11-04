"""Tests for `calculate_daily_sessions.collect_sessions`."""

from datetime import UTC, date, time

import pytest

from calculate_daily_sessions import collect_sessions
from domain.broker_clock import BROKER_SERVER_TZ
from domain.trading_session import ASIA_SESSION, LONDON_SESSION, TradingSession
from tests.calculate_daily_sessions._fakes import export


def _days(tmp_path, bars, session=ASIA_SESSION, source_timezone=BROKER_SERVER_TZ):
    days = collect_sessions([export(tmp_path / "bars.csv", bars)], [session], source_timezone=source_timezone)
    return days[session].set_index("date")


def test_summer_asia_session_is_03_00_to_12_00_broker_time(tmp_path) -> None:
    # 00:00-09:00 UTC is 03:00-12:00 on the broker clock under US summer time.
    days = _days(tmp_path, [
        ("2025.07.01 02:59", 1.0), ("2025.07.01 03:00", 1.1), ("2025.07.01 11:59", 1.2), ("2025.07.01 12:00", 1.3),
    ])

    day = days.loc[date(2025, 7, 1)]
    assert day.bar_count == 2
    assert day.open == pytest.approx(1.1)
    assert day.close == pytest.approx(1.2005)


def test_winter_asia_session_is_02_00_to_11_00_broker_time(tmp_path) -> None:
    days = _days(tmp_path, [
        ("2025.01.02 01:59", 1.0), ("2025.01.02 02:00", 1.1), ("2025.01.02 10:59", 1.2), ("2025.01.02 11:00", 1.3),
    ])

    assert days.loc[date(2025, 1, 2)].bar_count == 2
    assert days.loc[date(2025, 1, 2)].open == pytest.approx(1.1)


def test_source_timezone_labels_the_timestamps(tmp_path) -> None:
    days = _days(tmp_path, [("2025.07.01 00:00", 1.1), ("2025.07.01 09:00", 1.2)], source_timezone=UTC)

    assert days.loc[date(2025, 7, 1)].bar_count == 1
    assert days.loc[date(2025, 7, 1)].open == pytest.approx(1.1)


def test_high_and_low_span_the_whole_session(tmp_path) -> None:
    days = _days(tmp_path, [("2025.07.01 04:00", 1.1), ("2025.07.01 05:00", 1.3), ("2025.07.01 06:00", 1.2)])

    assert days.loc[date(2025, 7, 1)].high == pytest.approx(1.301)
    assert days.loc[date(2025, 7, 1)].low == pytest.approx(1.099)


def test_days_without_session_bars_are_left_out(tmp_path) -> None:
    days = _days(tmp_path, [("2025.07.01 04:00", 1.1), ("2025.07.02 15:00", 1.2), ("2025.07.03 04:00", 1.3)])

    assert list(days.index) == [date(2025, 7, 1), date(2025, 7, 3)]


def test_a_session_past_midnight_belongs_to_the_day_it_opens(tmp_path) -> None:
    overnight = TradingSession(time(22, 0, tzinfo=UTC), time(2, 0, tzinfo=UTC), name="Overnight")

    days = _days(tmp_path, [("2025.07.01 23:00", 1.1), ("2025.07.02 01:00", 1.2)],
                 session=overnight, source_timezone=UTC)

    assert list(days.index) == [date(2025, 7, 1)]
    assert days.loc[date(2025, 7, 1)].bar_count == 2


def test_each_session_gets_its_own_days(tmp_path) -> None:
    # 04:00 broker (01:00 UTC) is Asia only; 12:00 broker (09:00 UTC, 10:00 London) is London only.
    path = export(tmp_path / "bars.csv", [("2025.07.01 04:00", 1.1), ("2025.07.01 12:00", 1.2)])

    days = collect_sessions([path], [ASIA_SESSION, LONDON_SESSION], source_timezone=BROKER_SERVER_TZ)

    assert days[ASIA_SESSION].set_index("date").loc[date(2025, 7, 1)].open == pytest.approx(1.1)
    assert days[LONDON_SESSION].set_index("date").loc[date(2025, 7, 1)].open == pytest.approx(1.2)


def test_a_timestamp_in_two_files_counts_once_and_the_later_file_wins(tmp_path) -> None:
    # A monthly export can end with the next month's first bar, which the next export also holds.
    january = export(tmp_path / "EURUSD_2025_01.csv", [("2025.01.31 23:00", 1.0), ("2025.02.01 00:00", 1.1)])
    february = export(tmp_path / "EURUSD_2025_02.csv", [("2025.02.01 00:00", 1.2), ("2025.02.01 01:00", 1.3)])

    days = collect_sessions([january, february], [ASIA_SESSION], source_timezone=UTC)

    day = days[ASIA_SESSION].set_index("date").loc[date(2025, 2, 1)]
    assert day.bar_count == 2
    assert day.open == pytest.approx(1.2)
