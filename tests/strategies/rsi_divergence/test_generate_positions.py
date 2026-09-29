"""Tests for `strategies.rsi_divergence.RsiDivergence.generate_positions`."""

from datetime import UTC, time
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ

from domain.pandas_approach.divergence import Category, Direction
from domain.pandas_approach.position import Side
from strategies.rsi_divergence import RsiDivergence

from ._fakes import ENTRY, PIVOT, at, data, divergence, script


def test_bullish_divergence_is_a_long_with_stop_below_the_pivot_low(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    [position] = RsiDivergence(risk_reward=2.0, stop_buffer_pips=1.0).generate_positions(data(pivot_low=1.0980))

    assert position.side == Side.LONG
    assert position.open_dt == at(ENTRY)
    assert position.open_price == 1.1000
    assert position.sl == pytest.approx(1.0979)            # pivot low - 1 pip
    assert position.tp == pytest.approx(1.1042)            # 2 x the 21-pip risk
    assert position.exit_dt is None
    assert position.tag == f"bullish divergence, pivot {at(PIVOT):%Y-%m-%d %H:%M}"


def test_bearish_divergence_is_a_short_with_stop_above_the_pivot_high(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BEARISH, 75, 65))

    [position] = RsiDivergence(risk_reward=1.5, stop_buffer_pips=0).generate_positions(data(pivot_high=1.1020))

    assert position.side == Side.SHORT
    assert position.sl == pytest.approx(1.1020)
    assert position.tp == pytest.approx(1.0970)            # 1.5 x the 20-pip risk


def test_entry_is_the_open_after_pivot_confirmation(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    [position] = RsiDivergence(pivot_right=3).generate_positions(data())

    assert position.open_dt == at(PIVOT + 3 + 1)


def test_divergences_failing_the_band_filter_are_skipped(monkeypatch) -> None:
    script(
        monkeypatch,
        divergence(Direction.BULLISH, 40, 45),     # starts inside the band
        divergence(Direction.BULLISH, 20, 25),     # never re-enters it
    )

    assert RsiDivergence().generate_positions(data()) == []


def test_hidden_divergences_are_never_traded(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35, category=Category.HIDDEN))

    assert RsiDivergence().generate_positions(data()) == []


def test_long_whose_entry_is_already_below_the_pivot_low_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    assert RsiDivergence().generate_positions(data(pivot_low=1.0980, entry_open=1.0975)) == []


def test_short_whose_entry_is_already_above_the_pivot_high_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BEARISH, 75, 65))

    assert RsiDivergence().generate_positions(data(pivot_high=1.1020, entry_open=1.1025)) == []


def test_divergence_too_close_to_the_end_to_confirm_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35, end_bar=57))    # 57 + 6 is past bar 59

    assert RsiDivergence().generate_positions(data(n=60)) == []


def test_one_position_per_signal(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35), divergence(Direction.BEARISH, 75, 65, end_bar=40))

    positions = RsiDivergence().generate_positions(data())

    assert [p.side for p in positions] == [Side.LONG, Side.SHORT]


def test_runs_on_real_divergence_detection() -> None:
    # No scripting: the flat fixture has no RSI pivots, so no trades -- and no crash.
    assert RsiDivergence().generate_positions(data()) == []


# The entry bar opens 06:30 on the broker clock: 04:30 UTC, 04:30 London (winter).
def broker(hour: int, minute: int = 0) -> time:
    return time(hour, minute, tzinfo=BROKER_SERVER_TZ)


@pytest.mark.parametrize("start_time, end_time", [
    (broker(6, 30), None),                  # start is inclusive
    (None, broker(6, 45)),
    (broker(6, 0), broker(7, 0)),
    (broker(22, 0), broker(7, 0)),          # wraps past midnight
    (time(4, 30, tzinfo=ZoneInfo("Europe/London")), time(5, 0, tzinfo=UTC)),
])
def test_entry_inside_the_window_is_taken(monkeypatch, start_time, end_time) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    [position] = RsiDivergence(start_time=start_time, end_time=end_time).generate_positions(data())

    assert position.open_dt == at(ENTRY)


@pytest.mark.parametrize("start_time, end_time", [
    (broker(6, 45), None),
    (None, broker(6, 30)),                  # end is exclusive
    (broker(7, 0), broker(8, 0)),
    (time(6, 30, tzinfo=UTC), None),        # 06:30 UTC is 08:30 on the broker clock
])
def test_entry_outside_the_window_is_skipped(monkeypatch, start_time, end_time) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    assert RsiDivergence(start_time=start_time, end_time=end_time).generate_positions(data()) == []


def test_window_is_compared_on_the_datas_clock(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))
    strategy = RsiDivergence(start_time=time(6, 30, tzinfo=UTC))

    assert strategy.generate_positions(data()) == []                    # bars on the broker clock
    assert len(strategy.generate_positions(data(timezone=UTC))) == 1    # the same stamps as UTC


def test_window_limits_entries_not_the_signal_scan(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35), divergence(Direction.BEARISH, 75, 65, end_bar=40))

    # Bar 40 + 6 = 46 opens 11:30 broker; only the short falls inside 10:00-12:00.
    [position] = RsiDivergence(start_time=broker(10), end_time=broker(12)).generate_positions(data())

    assert position.side == Side.SHORT
