"""Tests for `strategies.session_breakout.SessionBreakout.generate_positions`."""

from datetime import UTC, date, time

import pandas as pd
import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.position import PositionOutcome, Side
from domain.pandas_approach.shift_timezone import shift_timezone
from strategies.session_breakout import SessionBreakout

from ._fakes import BOTH_WAYS, BREAK_DOWN, BREAK_UP, FLAT, QUIET, TUESDAY, WEDNESDAY, data, day_frame


def _positions(*frames, **kwargs):
    strategy = kwargs.pop("strategy", SessionBreakout())
    return strategy.generate_positions(data(*frames, **kwargs))


def _at(hhmm: str, day: date = TUESDAY) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}")


# --- the setup -----------------------------------------------------------------------

def test_upside_break_is_a_long_at_the_session_high() -> None:
    [position] = _positions(day_frame(overrides={"10:30": BREAK_UP}))

    assert position.side == Side.LONG
    assert position.open_dt == _at("10:30")
    assert position.open_price == 1.1005
    assert position.sl == pytest.approx(1.1000)          # session midpoint
    assert position.tp == pytest.approx(1.10125)         # 1.5 x the 5-pip risk above entry
    assert position.exit_dt == _at("09:00", WEDNESDAY)   # the session's end the next day
    assert position.tag == "break-high"
    assert position.outcome == PositionOutcome.OPEN


def test_downside_break_is_a_short_at_the_session_low() -> None:
    [position] = _positions(day_frame(overrides={"11:00": BREAK_DOWN}))

    assert position.side == Side.SHORT
    assert position.open_dt == _at("11:00")
    assert position.open_price == 1.0995
    assert position.sl == pytest.approx(1.1000)
    assert position.tp == pytest.approx(1.09875)
    assert position.tag == "break-low"


def test_target_scales_with_risk_reward() -> None:
    [position] = _positions(day_frame(overrides={"10:30": BREAK_UP}), strategy=SessionBreakout(risk_reward=2.0))

    assert position.tp == pytest.approx(1.1015)


def test_only_the_first_break_of_a_level_opens_a_position() -> None:
    [position] = _positions(day_frame(overrides={"10:30": BREAK_UP, "12:00": BREAK_UP}))

    assert position.open_dt == _at("10:30")


def test_both_sides_can_trigger_on_the_same_day() -> None:
    long, short = _positions(day_frame(overrides={"10:30": BREAK_UP, "14:00": BREAK_DOWN}))

    assert (long.side, long.open_dt) == (Side.LONG, _at("10:30"))
    assert (short.side, short.open_dt) == (Side.SHORT, _at("14:00"))


def test_one_bar_through_both_levels_opens_both_sides() -> None:
    long, short = _positions(day_frame(overrides={"10:30": BOTH_WAYS}))

    assert (long.side, short.side) == (Side.LONG, Side.SHORT)
    assert long.open_dt == short.open_dt == _at("10:30")


def test_the_first_bar_after_the_session_can_trigger() -> None:
    [position] = _positions(day_frame(overrides={"09:00": BREAK_UP}))

    assert position.open_dt == _at("09:00")


def test_a_level_touched_inside_the_session_is_not_a_break() -> None:
    assert _positions(day_frame()) == []


# --- the breakout window runs to the session's end the next day -----------------------

def test_a_break_after_midnight_still_belongs_to_the_previous_day() -> None:
    # Not midnight, as tokyo-session-breakout.md says: the script's window runs to 09:00 next day.
    tuesday = day_frame(TUESDAY)
    wednesday = day_frame(WEDNESDAY, session=QUIET, overrides={"03:00": BREAK_UP})

    tuesdays = [p for p in _positions(tuesday, wednesday) if p.exit_dt == _at("09:00", WEDNESDAY)]

    assert [(p.side, p.open_dt) for p in tuesdays] == [(Side.LONG, _at("03:00", WEDNESDAY))]


def test_a_break_at_the_next_sessions_end_is_too_late() -> None:
    tuesday = day_frame(TUESDAY)
    wednesday = day_frame(WEDNESDAY, session=QUIET, overrides={"09:00": BREAK_UP})

    tuesdays = [p for p in _positions(tuesday, wednesday) if p.exit_dt == _at("09:00", WEDNESDAY)]

    assert tuesdays == []


# --- days that don't trade -------------------------------------------------------------

def test_a_range_above_the_maximum_cancels_the_day() -> None:
    frame = day_frame(overrides={"10:30": BREAK_UP})

    assert _positions(frame, strategy=SessionBreakout(max_range_pips=9.9)) == []
    # 1.1005 - 1.0995 is 10.000000000000009 pips in floats, in the script too.
    assert len(_positions(frame, strategy=SessionBreakout(max_range_pips=10.01))) == 1


def test_a_day_without_session_bars_does_not_trade() -> None:
    assert _positions(day_frame(overrides={"10:30": BREAK_UP}, drop_before="09:00")) == []


def test_a_flat_session_is_skipped() -> None:
    # The script would open two zero-risk positions; a Position cannot hold one.
    assert _positions(day_frame(session=FLAT, overrides={"10:30": BREAK_UP})) == []


# --- clocks ----------------------------------------------------------------------------

@pytest.mark.parametrize("day, offset_hours", [(TUESDAY, 2), (date(2026, 7, 7), 3)])
def test_broker_clock_data_trades_the_utc_session(day: date, offset_hours: int) -> None:
    utc = pd.concat([day_frame(day, overrides={"10:30": BREAK_UP})], ignore_index=True)
    broker = shift_timezone(utc, BROKER_SERVER_TZ, from_tz=UTC)

    [position] = _positions(broker, timezone=BROKER_SERVER_TZ)

    # Emitted on the data's own clock: GMT+2 in winter, GMT+3 in summer.
    assert position.open_dt == pd.Timestamp(f"{day} 10:30") + pd.Timedelta(hours=offset_hours)
    assert position.exit_dt == pd.Timestamp(f"{day} 09:00") + pd.Timedelta(days=1, hours=offset_hours)


def test_the_session_can_be_set_in_another_zone() -> None:
    # 00:00-09:00 UTC, spelled out in UTC instead of Asia/Tokyo: the same trades.
    strategy = SessionBreakout(session_start=time(0, 0), session_end=time(9, 0), session_timezone="UTC")

    [position] = _positions(day_frame(overrides={"10:30": BREAK_UP}), strategy=strategy)

    assert position.open_dt == _at("10:30")
    assert position.exit_dt == _at("09:00", WEDNESDAY)


def test_a_session_crossing_utc_midnight_never_trades() -> None:
    # Kept from the script: the session is cut at midnight and its window is empty.
    strategy = SessionBreakout(session_start=time(20, 0), session_end=time(2, 0), session_timezone="UTC")
    frames = [day_frame(TUESDAY, session=QUIET, overrides={"22:00": BREAK_UP}), day_frame(WEDNESDAY, session=QUIET)]

    assert _positions(*frames, strategy=strategy) == []
