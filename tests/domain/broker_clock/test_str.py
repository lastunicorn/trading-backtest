"""Tests for `domain.broker_clock.ShiftedZone.__str__` and `__repr__`."""

from domain.broker_clock import BROKER_SERVER_TZ


def test_str_is_the_name() -> None:
    assert str(BROKER_SERVER_TZ) == "broker-server (America/New_York+7h)"


def test_repr_shows_base_and_shift() -> None:
    assert repr(BROKER_SERVER_TZ) == (
        "ShiftedZone('America/New_York', datetime.timedelta(seconds=25200), 'broker-server (America/New_York+7h)')"
    )
