"""Processing that turns parsed bars into the datasets the research runs on.

The counterpart to `ports/`: where a port knows a file format, this package
knows what the data should look like -- how bars collapse into a coarser
timeframe, which of two rows claiming the same timestamp wins, what counts as a
raw source file, and what a data-quality report has to account for.

    from domain.frames import resample_ohlc
    from domain.dataset import build_clean_dataset

Depends on pandas; most of `ports/` deliberately does not (the exception is
`ports.mt5_file_access.mt5_frame_reader`, which builds a frame directly).
"""
