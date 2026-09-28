"""Tests for `strategies.narrow_asia_fade.NarrowAsiaFade.generate_positions`."""

from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from domain.pandas_approach.position import PositionOutcome, Side
from domain.sample_size import SampleSize
from strategies.narrow_asia_fade import NarrowAsiaFade

from ._fakes import (
    ABOVE_H, ASIA, BACK_ABOVE_L, BACK_BELOW_H, BELOW_L, BREAK_DOWN, BREAK_UP, MONDAY, QUIET, data, day_frame,
)


def _positions(*frames, **kwargs):
    strategy = kwargs.pop("strategy", NarrowAsiaFade())
    return strategy.generate_positions(data(*frames, **kwargs))


def _at(hhmm: str, day: date = MONDAY) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}")


# --- the setup -----------------------------------------------------------------------

def test_upside_break_then_reentry_is_a_short_at_the_asia_high() -> None:
    overrides = {"10:30": BREAK_UP, "10:35": ABOVE_H, "10:40": ABOVE_H, "10:45": BACK_BELOW_H}

    [position] = _positions(day_frame(overrides=overrides))

    assert position.side == Side.SHORT
    assert position.open_dt == _at("10:45")
    assert position.open_price == 1.1005
    assert position.tp == pytest.approx(1.1000)          # Asia midpoint
    assert position.sl == pytest.approx(1.1015)          # 1.00 x the 10-pip range above entry
    assert position.exit_dt == _at("14:05")              # the 14:00 bar is still traded
    assert position.tag == "fade-high"
    assert position.outcome == PositionOutcome.OPEN


def test_downside_break_then_reentry_is_a_long_at_the_asia_low() -> None:
    overrides = {"11:00": BREAK_DOWN, "11:05": BELOW_L, "11:10": BELOW_L, "11:15": BELOW_L, "11:20": BACK_ABOVE_L}

    [position] = _positions(day_frame(overrides=overrides))

    assert position.side == Side.LONG
    assert position.open_dt == _at("11:20")
    assert position.open_price == 1.0995
    assert position.tp == pytest.approx(1.1000)
    assert position.sl == pytest.approx(1.0985)
    assert position.tag == "fade-low"


def test_stop_scales_with_the_range_multiple() -> None:
    [position] = _positions(
        day_frame(overrides={"10:30": BREAK_UP, "10:45": BACK_BELOW_H}),
        strategy=NarrowAsiaFade(stop_range_multiple=0.5),
    )

    assert position.sl == pytest.approx(1.1010)


def test_one_position_per_qualifying_day() -> None:
    setup = {"10:30": BREAK_UP, "10:45": BACK_BELOW_H}
    tuesday, wednesday = date(2026, 1, 6), date(2026, 1, 7)

    positions = _positions(day_frame(MONDAY, setup), day_frame(tuesday), day_frame(wednesday, setup))

    assert [p.open_dt.date() for p in positions] == [MONDAY, wednesday]


# --- the Asia filter ---------------------------------------------------------------------

def test_asia_range_above_the_threshold_is_skipped() -> None:
    wide = (1.1000, 1.1030, 1.0995, 1.1000, 10)    # 35-pip Asia range

    assert _positions(day_frame(overrides={"05:00": wide, "10:30": BREAK_UP, "10:45": BACK_BELOW_H})) == []


def test_threshold_is_a_parameter() -> None:
    setup = {"10:30": BREAK_UP, "10:45": BACK_BELOW_H}

    assert _positions(day_frame(overrides=setup), strategy=NarrowAsiaFade(narrow_threshold_pips=9.0)) == []


def test_up_to_three_missing_asia_bars_are_tolerated() -> None:
    setup = {"10:30": BREAK_UP, "10:45": BACK_BELOW_H}

    tolerated = _positions(day_frame(overrides=setup, drop=["03:00", "04:00", "05:00"]))
    too_many = _positions(day_frame(overrides=setup, drop=["03:00", "04:00", "05:00", "06:00"]))

    assert len(tolerated) == 1
    assert too_many == []


def test_asia_window_ends_before_london_open() -> None:
    # A 10:00 bar reaching past H is a London break, not part of the Asia range.
    [position] = _positions(day_frame(overrides={"10:00": BREAK_UP, "10:10": BACK_BELOW_H}))

    assert position.open_price == 1.1005


# --- the break -------------------------------------------------------------------------

def test_no_break_no_trade() -> None:
    assert _positions(day_frame()) == []


def test_break_bar_touching_both_levels_skips_the_day() -> None:
    both = (1.1000, 1.1008, 1.0992, 1.1000, 30)

    assert _positions(day_frame(overrides={"10:30": both, "10:45": BACK_BELOW_H})) == []


def test_only_the_first_break_counts() -> None:
    # Downside break first; the later upside break is ignored.
    overrides = {"10:30": BREAK_DOWN, "10:45": BACK_ABOVE_L, "11:30": BREAK_UP, "11:45": BACK_BELOW_H}

    [position] = _positions(day_frame(overrides=overrides))

    assert position.side == Side.LONG


def test_break_with_low_relative_volume_is_skipped() -> None:
    weak = (*BREAK_UP[:4], 12)    # 12 / SMA20 ~ 1.19 < 1.6

    assert _positions(day_frame(overrides={"10:30": weak, "10:45": BACK_BELOW_H})) == []


def test_relative_volume_threshold_is_a_parameter() -> None:
    weak = (*BREAK_UP[:4], 12)

    positions = _positions(
        day_frame(overrides={"10:30": weak, "10:45": BACK_BELOW_H}),
        strategy=NarrowAsiaFade(rel_vol_min=1.1),
    )

    assert len(positions) == 1


def test_without_volume_there_is_no_trade() -> None:
    frame = day_frame(overrides={"10:30": BREAK_UP, "10:45": BACK_BELOW_H}).drop(columns="tick_volume")

    assert _positions(frame) == []


def test_break_after_the_study_end_is_ignored() -> None:
    assert _positions(day_frame(overrides={"14:05": BREAK_UP, "14:10": BACK_BELOW_H})) == []


# --- the re-entry ---------------------------------------------------------------------------

def test_break_bar_itself_is_not_a_reentry() -> None:
    # Breaks above H and closes back inside, but the entry must come from a later bar.
    break_and_back = (1.1004, 1.1008, 1.1002, 1.1003, 30)

    [position] = _positions(day_frame(overrides={"10:30": break_and_back, "10:50": BACK_BELOW_H}))

    assert position.open_dt == _at("10:35")    # the next bar (quiet, low 1.0997) already trades back below H


def test_no_reentry_by_the_study_end_no_trade() -> None:
    overrides = {"10:30": BREAK_UP}
    overrides.update({f"{h:02d}:{m:02d}": ABOVE_H for h in range(10, 15) for m in range(0, 60, 5) if (h, m) > (10, 30)})

    assert _positions(day_frame(overrides=overrides)) == []


def test_reentry_on_the_study_end_bar_counts() -> None:
    overrides = {f"{h:02d}:{m:02d}": ABOVE_H for h in range(10, 14) for m in range(0, 60, 5) if (h, m) > (10, 30)}
    overrides.update({"10:30": BREAK_UP, "14:00": BACK_BELOW_H})

    [position] = _positions(day_frame(overrides=overrides))

    assert position.open_dt == _at("14:00")


# --- the data it accepts -----------------------------------------------------------------------

def test_weekend_days_are_not_traded() -> None:
    saturday = date(2026, 1, 10)

    assert _positions(day_frame(saturday, {"10:30": BREAK_UP, "10:45": BACK_BELOW_H})) == []


def test_data_on_another_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="broker-server"):
        _positions(day_frame(), timezone=ZoneInfo("UTC"))


def test_non_minute_timeframe_is_rejected() -> None:
    with pytest.raises(ValueError, match="minute bars"):
        _positions(day_frame(), timeframe=SampleSize.Parse("1h"))


def test_quiet_bar_is_quiet() -> None:
    # Guards the fixture: a default bar outside Asia sits strictly inside the Asia range.
    assert ASIA[2] < QUIET[2] and QUIET[1] < ASIA[1]
