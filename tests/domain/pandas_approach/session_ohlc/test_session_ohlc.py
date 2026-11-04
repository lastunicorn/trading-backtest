"""Tests for `domain.pandas_approach.session_ohlc.session_ohlc`."""

from datetime import UTC, date, time
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.session_ohlc import SESSION_OHLC_COLUMNS, session_ohlc
from domain.trading_session import ASIA_SESSION, NEW_YORK_SESSION, TradingSession

OVERNIGHT = TradingSession(time(22, 0, tzinfo=UTC), time(2, 0, tzinfo=UTC), name="Overnight")


def _frame(bars: list[tuple[str, float]]) -> pd.DataFrame:
    """One bar per `("YYYY-MM-DD HH:MM", price)`: open = price, high/low = price -/+ 0.001, close = price + 0.0005."""
    prices = pd.Series([price for _, price in bars], dtype=float)
    return pd.DataFrame({
        "datetime": pd.to_datetime([stamp for stamp, _ in bars]),
        "open": prices,
        "high": prices + 0.001,
        "low": prices - 0.001,
        "close": prices + 0.0005,
    })


def _by_day(result: pd.DataFrame) -> pd.DataFrame:
    return result.set_index("date")


def test_columns_and_one_row_per_session_day() -> None:
    result = session_ohlc(_frame([("2025-07-01 01:00", 1.1), ("2025-07-02 01:00", 1.2)]), ASIA_SESSION, timezone=UTC)

    assert list(result.columns) == SESSION_OHLC_COLUMNS
    assert list(result["date"]) == [date(2025, 7, 1), date(2025, 7, 2)]


def test_ohlc_folds_the_session_bars() -> None:
    result = session_ohlc(_frame([
        ("2025-07-01 01:00", 1.1), ("2025-07-01 02:00", 1.3), ("2025-07-01 03:00", 1.2),
    ]), ASIA_SESSION, timezone=UTC)

    day = _by_day(result).loc[date(2025, 7, 1)]
    assert day.open == pytest.approx(1.1)
    assert day.high == pytest.approx(1.301)
    assert day.low == pytest.approx(1.099)
    assert day.close == pytest.approx(1.2005)
    assert day.bar_count == 3


def test_start_is_inclusive_and_end_exclusive() -> None:
    # Asia is 00:00-09:00 UTC.
    result = session_ohlc(_frame([
        ("2025-07-01 00:00", 1.1), ("2025-07-01 08:59", 1.2), ("2025-07-01 09:00", 1.3),
    ]), ASIA_SESSION, timezone=UTC)

    assert _by_day(result).loc[date(2025, 7, 1)].bar_count == 2


def test_timezone_labels_the_timestamps() -> None:
    # 03:00 broker is 00:00 UTC in summer: inside Asia. 02:59 is not.
    result = session_ohlc(_frame([("2025-07-01 02:59", 1.0), ("2025-07-01 03:00", 1.1)]),
                          ASIA_SESSION, timezone=BROKER_SERVER_TZ)

    day = _by_day(result).loc[date(2025, 7, 1)]
    assert day.bar_count == 1
    assert day.open == pytest.approx(1.1)


def test_a_dst_observing_session_moves_with_the_date() -> None:
    # New York 09:30 is 14:30 UTC in winter, 13:30 UTC in summer.
    frame = _frame([("2025-01-02 13:30", 1.0), ("2025-01-02 14:30", 1.1), ("2025-07-01 13:30", 1.2)])

    result = _by_day(session_ohlc(frame, NEW_YORK_SESSION, timezone=UTC))

    assert result.loc[date(2025, 1, 2)].open == pytest.approx(1.1)
    assert result.loc[date(2025, 7, 1)].open == pytest.approx(1.2)


def test_the_day_is_the_session_date_in_its_start_zone() -> None:
    # 23:00 UTC on June 30 is 08:00 July 1 in Tokyo; Asia opens 09:00 Tokyo, so it is outside.
    # 00:30 UTC on July 1 is 09:30 July 1 in Tokyo: the July 1 session.
    frame = _frame([("2025-06-30 23:00", 1.0), ("2025-07-01 00:30", 1.1)])
    tokyo_asia = TradingSession(time(9, 0, tzinfo=ZoneInfo("Asia/Tokyo")), time(18, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    result = session_ohlc(frame, tokyo_asia, timezone=UTC)

    assert list(result["date"]) == [date(2025, 7, 1)]
    assert result["bar_count"].iloc[0] == 1


def test_a_session_past_midnight_belongs_to_the_day_it_opens() -> None:
    result = session_ohlc(_frame([("2025-07-01 23:00", 1.1), ("2025-07-02 01:00", 1.2), ("2025-07-02 02:00", 1.3)]),
                          OVERNIGHT, timezone=UTC)

    assert list(result["date"]) == [date(2025, 7, 1)]
    assert result["bar_count"].iloc[0] == 2


def test_bars_outside_every_session_are_left_out() -> None:
    result = session_ohlc(_frame([("2025-07-01 12:00", 1.1)]), ASIA_SESSION, timezone=UTC)

    assert result.empty
    assert list(result.columns) == SESSION_OHLC_COLUMNS


def test_an_empty_frame_gives_no_days() -> None:
    result = session_ohlc(_frame([]), ASIA_SESSION, timezone=UTC)

    assert result.empty
    assert list(result.columns) == SESSION_OHLC_COLUMNS


def test_unsorted_rows_open_and_close_by_time() -> None:
    result = session_ohlc(_frame([("2025-07-01 03:00", 1.2), ("2025-07-01 01:00", 1.1)]), ASIA_SESSION, timezone=UTC)

    day = _by_day(result).loc[date(2025, 7, 1)]
    assert day.open == pytest.approx(1.1)
    assert day.close == pytest.approx(1.2005)
