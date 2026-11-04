"""Tests for `domain.broker_clock.SwitchingZone.__getinitargs__`: copy and pickle round-trip."""

import copy
import pickle

from domain.broker_clock import HISTDATA_TZ


def test_deepcopy_gives_an_equal_zone() -> None:
    assert copy.deepcopy(HISTDATA_TZ) == HISTDATA_TZ


def test_pickle_round_trips() -> None:
    restored = pickle.loads(pickle.dumps(HISTDATA_TZ))

    assert restored == HISTDATA_TZ
    assert str(restored) == str(HISTDATA_TZ)
