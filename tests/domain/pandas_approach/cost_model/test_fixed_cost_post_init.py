"""Tests for `domain.pandas_approach.cost_model.FixedCost.__post_init__`."""

import pytest

from domain.pandas_approach.cost_model import FixedCost


def test_defaults_to_the_research_pipeline_cost() -> None:
    assert FixedCost().pips == 1.7


def test_zero_cost_is_allowed() -> None:
    assert FixedCost(pips=0).pips == 0


def test_negative_cost_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        FixedCost(pips=-0.1)
