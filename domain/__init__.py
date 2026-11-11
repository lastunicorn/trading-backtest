"""The concepts behind the market data and the trades taken on it, independent
of any file or strategy they came from.

The counterpart to `ports/`: where a port knows a file format, this package
knows the concepts -- what one OHLC candle is (`bar.Bar`), how candles collapse
into a coarser timeframe (`frames.resample_ohlc`), which of two rows claiming
the same timestamp wins, and what a triggered trade looks like once it has an
entry, a stop-loss and a take-profit (`position.Position`).

One subpackage per concept, each grouped as its page in
`doc/architecture/domain/`: `market_data` (timeframes, symbols, clocks,
sessions, the bar frame, `HistoricalData`), `backtesting` (strategies'
positions, costs, exits, statistics) and `indicators` (RSI, divergences), plus
`bar_approach`, the stdlib `Bar` and the legacy engine built on it.

    from domain.bar_approach.bar import Bar
    from domain.market_data.frames import resample_ohlc
    from domain.backtesting.position import Position

`domain/market_data/frames.py` needs pandas; `domain/bar_approach/bar.py` is
stdlib only, and this `__init__` imports nothing, so
`ports.mt5_file_access.mt5_bar_reader` can import `domain.bar_approach.bar`
without gaining a pandas dependency. `domain/` never imports from `ports/` or
`application/`; wiring those together is `application/`'s job.
"""
