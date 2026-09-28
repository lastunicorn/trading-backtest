"""Acceptance test: the framework reproduces v28's frozen result on the canonical dataset.

v28's RANGE_MULT 1.00 line (output/narrow_asia_v28_output/v28_report.txt):
207 trades, 72.0% WR, PF 1.37, +257.5 pips net, max drawdown 70.5 pips.

`output/` is local-only (gitignored), so this skips where the dataset is absent.
A failure here is a framework or port bug, not a new research finding.
"""

from pathlib import Path

import pytest

from application.load_historical_data_use_case import load_clean_csv
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, ResolveFrom
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from strategies.narrow_asia_fade import NarrowAsiaFade

DATASET = Path(__file__).resolve().parents[3] / "output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv"


@pytest.mark.skipif(not DATASET.is_file(), reason="canonical clean M5 dataset not present")
def test_reproduces_v28_range_mult_1_00() -> None:
    data = load_clean_csv(DATASET, SampleSize.Parse("5m"), EurUsd())
    backtest = Backtest(
        NarrowAsiaFade(), data, ambiguity_policy=AmbiguityPolicy.ASSUME_SL, resolve_from=ResolveFrom.NEXT_BAR,
    )

    stats = backtest.run().statistics.loc["all"]

    assert stats["trades"] == 207
    assert round(stats["win_rate_pct"], 1) == 72.0
    assert round(stats["profit_factor"], 2) == 1.37
    assert round(stats["total_net_pips"], 1) == 257.5
    assert round(stats["max_drawdown_pips"], 1) == 70.5
