"""histdata.com MetaTrader downloads as the repo's bar frames.

The format is `libs.metatrader_csv`; this port knows what is particular to
histdata's files (no volume worth keeping, no spread, its own clock). See
`histdata_frame_reader`.

Re-exported so callers can use the short form:

    from ports.histdata_file_access import FILE_PATTERN, TIMEZONE, read_frame

    read_frame(".../histdata/mt/2025/DAT_MT_EURUSD_M1_202501.csv")
"""

from ports.histdata_file_access.histdata_frame_reader import FILE_PATTERN, FRAME_COLUMNS, TIMEZONE, read_frame

__all__ = ["FILE_PATTERN", "FRAME_COLUMNS", "TIMEZONE", "read_frame"]
