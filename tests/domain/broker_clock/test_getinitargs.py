"""Tests for `domain.broker_clock.ShiftedZone.__getinitargs__`: copy and pickle round-trip."""

import copy
import pickle
from datetime import time

from domain.broker_clock import BROKER_SERVER_TZ


def test_deepcopy_is_an_equal_zone() -> None:
    assert copy.deepcopy(BROKER_SERVER_TZ) == BROKER_SERVER_TZ


def test_pickle_round_trips() -> None:
    restored = pickle.loads(pickle.dumps(BROKER_SERVER_TZ))

    assert restored == BROKER_SERVER_TZ
    assert str(restored) == str(BROKER_SERVER_TZ)


def test_a_time_on_the_broker_clock_can_be_deep_copied() -> None:
    assert copy.deepcopy(time(10, 0, tzinfo=BROKER_SERVER_TZ)) == time(10, 0, tzinfo=BROKER_SERVER_TZ)
