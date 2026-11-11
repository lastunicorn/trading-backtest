"""Tests for `strategies.orb_retest_entry.OrbRetestEntry.generate_positions`."""

from datetime import UTC, date

import pandas as pd
import pytest

from domain.market_data.broker_clock import BROKER_SERVER_TZ
from domain.backtesting.position import EntryFill, PositionOutcome, Side
from domain.market_data.trading_session import LONDON_SESSION
from strategies.orb_retest_entry import OrbRetestEntry

from ._fakes import (ABOVE_MID, BELOW_MID, BOTH_WAYS, BREAK_DOWN, BREAK_TO_MID, BREAK_UP, FLAT, MISMATCH_TUESDAY,
                     PLUNGE, QUIET, RETEST_FROM_ABOVE, RETEST_FROM_BELOW, SUMMER_TUESDAY, TUESDAY, WEDNESDAY, data,
                     day_frame, range_at)


def _positions(*frames, strategy: OrbRetestEntry | None = None, **kwargs):
    return (strategy or OrbRetestEntry()).generate_positions(data(*frames, **kwargs))


def _long_day(overrides: dict[str, tuple], day: date = TUESDAY, **kwargs):
    """A day whose bars stay above the midpoint unless `overrides` says otherwise."""
    return day_frame(day, overrides=overrides, quiet_bar=ABOVE_MID, **kwargs)


def _short_day(overrides: dict[str, tuple], day: date = TUESDAY, **kwargs):
    """A day whose bars stay below the midpoint unless `overrides` says otherwise."""
    return day_frame(day, overrides=overrides, quiet_bar=BELOW_MID, **kwargs)


def _utc(hhmm: str, day: date = TUESDAY) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}")


# --- the setup -----------------------------------------------------------------------

def test_a_retest_after_an_upside_break_is_a_long_at_the_midpoint() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}))

    assert position.side == Side.LONG
    assert position.open_dt == _utc("15:20")        # 10:20 EST
    assert position.open_price == pytest.approx(1.1000)
    assert position.sl == 1.0995                    # the range's other side
    assert position.tp == pytest.approx(1.1015)     # 3 x the 5-pip risk above entry
    assert position.exit_dt == _utc("21:00")        # 16:00 EST
    assert position.entry_fill == EntryFill.AT_LEVEL
    assert position.tag == "retest-high"
    assert position.outcome == PositionOutcome.OPEN


def test_a_retest_after_a_downside_break_is_a_short_at_the_midpoint() -> None:
    [position] = _positions(_short_day({"10:30": BREAK_DOWN, "10:50": RETEST_FROM_BELOW}))

    assert position.side == Side.SHORT
    assert position.open_dt == _utc("15:50")
    assert position.open_price == pytest.approx(1.1000)
    assert position.sl == 1.1005
    assert position.tp == pytest.approx(1.0985)
    assert position.tag == "retest-low"


def test_target_scales_with_risk_reward() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}),
                            strategy=OrbRetestEntry(risk_reward=2.0))

    assert position.tp == pytest.approx(1.1010)


def test_a_break_without_a_retest_does_not_trade() -> None:
    assert _positions(_long_day({"10:00": BREAK_UP})) == []


def test_no_break_no_position() -> None:
    # The default quiet bars touch the midpoint all day, but nothing breaks the range.
    assert _positions(day_frame(quiet_bar=QUIET)) == []


def test_a_retest_before_the_break_does_not_count() -> None:
    assert _positions(_long_day({"10:00": RETEST_FROM_ABOVE, "10:10": BREAK_UP})) == []


def test_the_break_bar_cannot_fill_the_order() -> None:
    # It reaches the midpoint too, but OHLC can't say whether before or after the break.
    assert _positions(_long_day({"10:00": BREAK_TO_MID})) == []


def test_the_bar_after_the_break_can_fill_the_order() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_TO_MID, "10:01": RETEST_FROM_ABOVE}))

    assert position.open_dt == _utc("15:01")


def test_at_most_one_trade_a_day() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE, "10:40": RETEST_FROM_ABOVE,
                                       "11:00": BREAK_UP, "11:10": RETEST_FROM_ABOVE}))

    assert position.open_dt == _utc("15:20")


def test_the_first_break_sets_the_side() -> None:
    # Falling back through L after an upside break passes the midpoint: the long fills on the way.
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": PLUNGE}))

    assert (position.side, position.open_dt) == (Side.LONG, _utc("15:20"))


def test_a_bar_breaking_both_sides_skips_the_day() -> None:
    # Even with a clean break and retest later on.
    assert _positions(_long_day({"10:00": BOTH_WAYS, "10:10": BREAK_UP, "10:20": RETEST_FROM_ABOVE})) == []


# --- the windows ---------------------------------------------------------------------

def test_the_first_bar_after_the_range_can_break() -> None:
    [position] = _positions(_long_day({"09:45": BREAK_UP, "09:50": RETEST_FROM_ABOVE}))

    assert position.open_dt == _utc("14:50")


def test_the_last_bar_before_the_orders_expire_can_fill() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "11:29": RETEST_FROM_ABOVE}))

    assert position.open_dt == _utc("16:29")


def test_a_retest_after_the_orders_expire_is_ignored() -> None:
    assert _positions(_long_day({"10:00": BREAK_UP, "11:30": RETEST_FROM_ABOVE})) == []


@pytest.mark.parametrize("break_at, retest_at", [("09:00", "10:00"), ("11:30", "11:40"), ("13:00", "13:10")])
def test_a_break_outside_the_order_window_is_ignored(break_at: str, retest_at: str) -> None:
    assert _positions(_long_day({break_at: BREAK_UP, retest_at: RETEST_FROM_ABOVE})) == []


def test_the_range_includes_its_bars_wicks() -> None:
    # A wick at 09:44 widens the range, so 1.1008 is no longer a break of it.
    positions = _positions(_long_day({"09:44": (1.1000, 1.1010, 1.0995, 1.1000),
                                      "10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}))

    assert positions == []


def test_no_time_stop_leaves_exit_dt_unset() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}),
                            strategy=OrbRetestEntry(exit_at_session_end=False))

    assert position.exit_dt is None


def test_windows_follow_new_york_daylight_saving() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}, SUMMER_TUESDAY))

    assert position.open_dt == _utc("14:20", SUMMER_TUESDAY)   # 10:20 EDT
    assert position.exit_dt == _utc("20:00", SUMMER_TUESDAY)


def test_order_expiry_counts_from_the_session_start() -> None:
    strategy = OrbRetestEntry(order_expiry_minutes=60)    # 09:30 + 60 minutes: the order expires at 10:30 ET

    assert _positions(_long_day({"10:00": BREAK_UP, "10:30": RETEST_FROM_ABOVE}), strategy=strategy) == []
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:29": RETEST_FROM_ABOVE}), strategy=strategy)
    assert position.open_dt == _utc("15:29")


# --- the session ---------------------------------------------------------------------

def test_another_session_moves_every_window() -> None:
    # London 08:00-16:30 is 03:00-11:30 ET in January: range 03:00-03:15, orders until 05:00, flat by 11:30.
    frame = _long_day({**range_at("03:00"), "03:20": BREAK_UP, "04:59": RETEST_FROM_ABOVE}, range_bar=ABOVE_MID)

    [position] = _positions(frame, strategy=OrbRetestEntry(session=LONDON_SESSION))

    assert (position.side, position.open_price) == (Side.LONG, pytest.approx(1.1000))
    assert position.open_dt == _utc("09:59")     # 04:59 EST
    assert position.exit_dt == _utc("16:30")     # 16:30 London


def test_the_session_follows_its_own_daylight_saving() -> None:
    # New York is already on EDT, London not yet on BST: 08:00 London is 04:00 ET, 08:00 UTC.
    frame = _long_day({**range_at("04:00"), "04:20": BREAK_UP, "04:30": RETEST_FROM_ABOVE}, MISMATCH_TUESDAY,
                      range_bar=ABOVE_MID)

    [position] = _positions(frame, strategy=OrbRetestEntry(session=LONDON_SESSION))

    assert position.open_dt == _utc("08:30", MISMATCH_TUESDAY)
    assert position.exit_dt == _utc("16:30", MISMATCH_TUESDAY)


# --- days that don't trade -----------------------------------------------------------

def test_a_flat_range_does_not_trade() -> None:
    assert _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}, range_bar=FLAT)) == []


def test_a_day_without_range_bars_does_not_trade() -> None:
    assert _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}, drop=("09:30", "09:45"))) == []


def test_each_day_has_its_own_range() -> None:
    tuesday, wednesday = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}, TUESDAY),
                                    _short_day({"10:30": BREAK_DOWN, "10:50": RETEST_FROM_BELOW}, WEDNESDAY))

    assert (tuesday.side, tuesday.open_dt) == (Side.LONG, _utc("15:20", TUESDAY))
    assert (wednesday.side, wednesday.open_dt) == (Side.SHORT, _utc("15:50", WEDNESDAY))


# --- clocks and bar sizes ------------------------------------------------------------

def test_positions_are_on_the_data_clock() -> None:
    frame = _long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE})
    [on_utc] = _positions(frame, timezone=UTC)
    [on_broker] = _positions(frame, timezone=BROKER_SERVER_TZ)

    assert on_broker.open_dt == _utc("17:20")    # 10:20 New York + 7h
    assert on_broker.exit_dt == _utc("23:00")
    assert (on_broker.open_price, on_broker.sl, on_broker.tp) == (on_utc.open_price, on_utc.sl, on_utc.tp)


def test_m5_bars_tile_the_range() -> None:
    [position] = _positions(_long_day({"10:00": BREAK_UP, "10:20": RETEST_FROM_ABOVE}, minutes=5), timeframe="5m")

    assert position.open_dt == _utc("15:20")


@pytest.mark.parametrize("timeframe", ["30m", "7m", "1h"])
def test_bars_not_tiling_the_range_are_rejected(timeframe: str) -> None:
    with pytest.raises(ValueError, match="OrbRetestEntry needs minute bars"):
        _positions(day_frame(), timeframe=timeframe)
