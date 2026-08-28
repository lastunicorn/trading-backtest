"""What the market data means, independent of any file it came from.

The counterpart to `ports/`: where a port knows a file format, this package
knows the concepts -- what one OHLC candle is (`bar.Bar`), how candles collapse
into a coarser timeframe (`frames.resample_ohlc`), which of two rows claiming
the same timestamp wins.

    from domain.bar import Bar
    from domain.frames import resample_ohlc

`domain/frames.py` needs pandas; `domain/bar.py` is stdlib only, and this
`__init__` imports nothing, so `ports.mt5_file_access.mt5_bar_reader` can import
`domain.bar` without gaining a pandas dependency. `domain/` never imports from
`ports/` or `application/`; wiring those together is `application/`'s job.
"""
