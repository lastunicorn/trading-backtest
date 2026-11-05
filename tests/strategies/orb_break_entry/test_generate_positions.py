"""Tests for `strategies.orb_break_entry.OrbBreakEntry.generate_positions`."""

from datetime import UTC, date

import pandas as pd
import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.position import PositionOutcome, Side
from strategies.orb_break_entry import OrbBreakEntry

from ._fakes import (BOTH_WAYS, BREAK_DOWN, BREAK_UP, FLAT, SUMMER_TUESDAY, TUESDAY, WEDNESDAY, data,
                     day_frame)


def _positions(*frames, strategy: OrbBreakEntry | None = None, **kwargs):
    return (strategy or OrbBreakEntry()).generate_positions(data(*frames, **kwargs))


def _utc(hhmm: str, day: date = TUESDAY) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}")


# --- the setup -----------------------------------------------------------------------

def test_upside_break_is_a_long_at_the_range_high() -> None:
    [position] = _positions(day_frame(overrides={"10:00": BREAK_UP}))

    assert position.side == Side.LONG
    assert position.open_dt == _utc("15:00")        # 10:00 EST
    assert position.open_price == 1.1005
    assert position.sl == pytest.approx(1.1000)     # range midpoint
    assert position.tp == pytest.approx(1.1015)     # 2 x the 5-pip risk above entry
    assert position.exit_dt == _utc("21:00")        # 16:00 EST
    assert position.tag == "break-high"
    assert position.outcome == PositionOutcome.OPEN


def test_downside_break_is_a_short_at_the_range_low() -> None:
    [position] = _positions(day_frame(overrides={"10:30": BREAK_DOWN}))

    assert position.side == Side.SHORT
    assert position.open_dt == _utc("15:30")
    assert position.open_price == 1.0995
    assert position.sl == pytest.approx(1.1000)
    assert position.tp == pytest.approx(1.0985)
    assert position.tag == "break-low"


def test_target_scales_with_risk_reward() -> None:
    [position] = _positions(day_frame(overrides={"10:00": BREAK_UP}), strategy=OrbBreakEntry(risk_reward=1.5))

    assert position.tp == pytest.approx(1.10125)


def test_only_the_first_break_of_a_level_opens_a_position() -> None:
    [position] = _positions(day_frame(overrides={"10:00": BREAK_UP, "10:40": BREAK_UP}))

    assert position.open_dt == _utc("15:00")


def test_both_sides_can_trigger_on_the_same_day() -> None:
    long, short = _positions(day_frame(overrides={"10:00": BREAK_UP, "11:00": BREAK_DOWN}))

    assert (long.side, long.open_dt) == (Side.LONG, _utc("15:00"))
    assert (short.side, short.open_dt) == (Side.SHORT, _utc("16:00"))


def test_one_bar_through_both_levels_opens_both_sides() -> None:
    long, short = _positions(day_frame(overrides={"10:00": BOTH_WAYS}))

    assert (long.side, short.side) == (Side.LONG, Side.SHORT)
    assert long.open_dt == short.open_dt == _utc("15:00")


def test_no_break_no_position() -> None:
    assert _positions(day_frame()) == []


# --- the windows ---------------------------------------------------------------------

def test_the_first_bar_after_the_range_can_trigger() -> None:
    [position] = _positions(day_frame(overrides={"09:45": BREAK_UP}))

    assert position.open_dt == _utc("14:45")


def test_the_last_bar_before_the_orders_expire_can_trigger() -> None:
    [position] = _positions(day_frame(overrides={"11:29": BREAK_UP}))

    assert position.open_dt == _utc("16:29")


@pytest.mark.parametrize("hhmm", ["11:30", "13:00", "09:00"])
def test_a_break_outside_the_order_window_is_ignored(hhmm: str) -> None:
    assert _positions(day_frame(overrides={hhmm: BREAK_UP})) == []


def test_the_range_includes_its_bars_wicks() -> None:
    # A wick at 09:44 widens the range, so 1.1007 is no longer a break of it.
    positions = _positions(day_frame(overrides={"09:44": (1.1000, 1.1010, 1.0995, 1.1000),
                                                "10:00": BREAK_UP}))

    assert positions == []


def test_no_time_stop_leaves_exit_dt_unset() -> None:
    [position] = _positions(day_frame(overrides={"10:00": BREAK_UP}), strategy=OrbBreakEntry(exit_at=None))

    assert position.exit_dt is None


def test_windows_follow_new_york_daylight_saving() -> None:
    [position] = _positions(day_frame(SUMMER_TUESDAY, overrides={"10:00": BREAK_UP}))

    assert position.open_dt == _utc("14:00", SUMMER_TUESDAY)   # 10:00 EDT
    assert position.exit_dt == _utc("20:00", SUMMER_TUESDAY)


def test_custom_windows() -> None:
    strategy = OrbBreakEntry(range_minutes=30)
    # 09:50 is now inside the range, so it sets H rather than breaking it; 10:00 breaks the wider range.
    [position] = _positions(day_frame(overrides={"09:50": BREAK_UP, "10:00": BREAK_UP}), strategy=strategy)

    assert position.open_dt == _utc("15:00")
    assert position.open_price == 1.1008


# --- days that don't trade -----------------------------------------------------------

def test_a_flat_range_does_not_trade() -> None:
    assert _positions(day_frame(range_bar=FLAT, overrides={"10:00": BREAK_UP})) == []


def test_a_day_without_range_bars_does_not_trade() -> None:
    assert _positions(day_frame(drop=("09:30", "09:45"), overrides={"10:00": BREAK_UP})) == []


def test_each_day_has_its_own_range() -> None:
    tuesday, wednesday = _positions(day_frame(TUESDAY, overrides={"10:00": BREAK_UP}),
                                    day_frame(WEDNESDAY, overrides={"10:30": BREAK_DOWN}))

    assert (tuesday.side, tuesday.open_dt) == (Side.LONG, _utc("15:00", TUESDAY))
    assert (wednesday.side, wednesday.open_dt) == (Side.SHORT, _utc("15:30", WEDNESDAY))


# --- clocks and bar sizes ------------------------------------------------------------

def test_positions_are_on_the_data_clock() -> None:
    frame = day_frame(overrides={"10:00": BREAK_UP})
    [on_utc] = _positions(frame, timezone=UTC)
    [on_broker] = _positions(frame, timezone=BROKER_SERVER_TZ)

    assert on_broker.open_dt == _utc("17:00")    # 10:00 New York + 7h
    assert on_broker.exit_dt == _utc("23:00")
    assert (on_broker.open_price, on_broker.sl, on_broker.tp) == (on_utc.open_price, on_utc.sl, on_utc.tp)


def test_m5_bars_tile_the_range() -> None:
    [position] = _positions(day_frame(minutes=5, overrides={"10:00": BREAK_UP}), timeframe="5m")

    assert position.open_dt == _utc("15:00")


@pytest.mark.parametrize("timeframe", ["30m", "7m", "1h"])
def test_bars_not_tiling_the_range_are_rejected(timeframe: str) -> None:
    with pytest.raises(ValueError, match="opening range"):
        _positions(day_frame(), timeframe=timeframe)
