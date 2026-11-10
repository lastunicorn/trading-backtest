"""Formats and writes a backtest's result files: the trades, the statistics report and table, the run's record.

Re-exported so callers can use the short form:

    from ports.backtest_result_access import RunProvenance, format_report, run_info, write_results
"""

from ports.backtest_result_access.backtest_result_writer import RunProvenance, format_report, run_info, write_results

__all__ = ["RunProvenance", "format_report", "run_info", "write_results"]
