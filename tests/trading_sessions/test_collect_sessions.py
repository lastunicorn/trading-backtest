"""Tests for `trading_sessions.collect_sessions`."""

from datetime import UTC, date, time

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.trading_session_template import ASIA_SESSION, LONDON_SESSION, TradingSessionTemplate
from tests.trading_sessions._fakes import export
from trading_sessions import collect_sessions


def _block(tmp_path, bars, template=ASIA_SESSION, source_timezone=BROKER_SERVER_TZ):
    days = collect_sessions([export(tmp_path / "bars.csv", bars)], [template], source_timezone=source_timezone)
    return {day: session.bar_block for day, session in days[template].items()}


def test_summer_asia_session_is_03_00_to_12_00_broker_time(tmp_path) -> None:
    # 00:00-09:00 UTC is 03:00-12:00 on the broker clock under US summer time.
    blocks = _block(tmp_path, [
        ("2025.07.01 02:59", 1.0), ("2025.07.01 03:00", 1.1), ("2025.07.01 11:59", 1.2), ("2025.07.01 12:00", 1.3),
    ])

    block = blocks[date(2025, 7, 1)]
    assert block.bar_count == 2
    assert block.open_value == pytest.approx(1.1)
    assert block.close_value == pytest.approx(1.2005)


def test_winter_asia_session_is_02_00_to_11_00_broker_time(tmp_path) -> None:
    blocks = _block(tmp_path, [
        ("2025.01.02 01:59", 1.0), ("2025.01.02 02:00", 1.1), ("2025.01.02 10:59", 1.2), ("2025.01.02 11:00", 1.3),
    ])

    assert blocks[date(2025, 1, 2)].bar_count == 2
    assert blocks[date(2025, 1, 2)].open_value == pytest.approx(1.1)


def test_source_timezone_labels_the_timestamps(tmp_path) -> None:
    blocks = _block(tmp_path, [("2025.07.01 00:00", 1.1), ("2025.07.01 09:00", 1.2)], source_timezone=UTC)

    assert blocks[date(2025, 7, 1)].bar_count == 1
    assert blocks[date(2025, 7, 1)].open_value == pytest.approx(1.1)


def test_high_and_low_span_the_whole_session(tmp_path) -> None:
    blocks = _block(tmp_path, [("2025.07.01 04:00", 1.1), ("2025.07.01 05:00", 1.3), ("2025.07.01 06:00", 1.2)])

    assert blocks[date(2025, 7, 1)].high_value == pytest.approx(1.301)
    assert blocks[date(2025, 7, 1)].low_value == pytest.approx(1.099)


def test_days_without_session_bars_are_left_out(tmp_path) -> None:
    blocks = _block(tmp_path, [("2025.07.01 04:00", 1.1), ("2025.07.02 15:00", 1.2), ("2025.07.03 04:00", 1.3)])

    assert sorted(blocks) == [date(2025, 7, 1), date(2025, 7, 3)]


def test_a_session_past_midnight_belongs_to_the_day_it_opens(tmp_path) -> None:
    overnight = TradingSessionTemplate(time(22, 0, tzinfo=UTC), time(2, 0, tzinfo=UTC), name="Overnight")

    blocks = _block(tmp_path, [("2025.07.01 23:00", 1.1), ("2025.07.02 01:00", 1.2)],
                    template=overnight, source_timezone=UTC)

    assert list(blocks) == [date(2025, 7, 1)]
    assert blocks[date(2025, 7, 1)].bar_count == 2


def test_each_template_gets_its_own_days(tmp_path) -> None:
    # 04:00 broker (01:00 UTC) is Asia only; 12:00 broker (09:00 UTC, 10:00 London) is London only.
    path = export(tmp_path / "bars.csv", [("2025.07.01 04:00", 1.1), ("2025.07.01 12:00", 1.2)])

    days = collect_sessions([path], [ASIA_SESSION, LONDON_SESSION], source_timezone=BROKER_SERVER_TZ)

    assert days[ASIA_SESSION][date(2025, 7, 1)].bar_block.open_value == pytest.approx(1.1)
    assert days[LONDON_SESSION][date(2025, 7, 1)].bar_block.open_value == pytest.approx(1.2)
