"""A Dukascopy candle export, identified by its file name.

dukascopy-node names each export `<instrument>-<timeframe>-<side>-<start>-<end>.csv`:

    eurusd-m1-bid-2020-01-01-2020-02-01.csv     a whole period: `end` is a date (exclusive)
    eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv  a partial one: `end` is the download time

The file's contents carry neither the instrument nor the price side, so the
name is the only place they are recorded. Parsing it needs no disk access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

__all__ = ["DukascopyFile", "DukascopyFilePair", "PriceSide"]

_NAME = re.compile(
    r"(?P<instrument>[a-z0-9]+)-(?P<timeframe>[a-z0-9]+)-(?P<side>bid|ask)"
    r"-(?P<start>\d{4}-\d{2}-\d{2})-(?P<end>\d{4}-\d{2}-\d{2}(?:T\d{2}-\d{2})?)\.csv"
)

_DATE_FORMAT = "%Y-%m-%d"
_DOWNLOAD_TIME_FORMAT = "%Y-%m-%dT%H-%M"


class PriceSide(Enum):
    BID = "bid"
    ASK = "ask"


@dataclass(frozen=True)
class DukascopyFile:
    """One price side of one period of one instrument, as named on disk."""

    path: Path
    instrument: str          # "eurusd", "xauusd", "deuidxeur" -- as written in the name
    timeframe: str           # "m1", "h1", ... -- as written in the name
    side: PriceSide
    start: date              # the first day the file covers
    end: date | datetime     # a date (exclusive) for a whole period, a datetime for a partial download

    @classmethod
    def parse(cls, path: str | Path) -> DukascopyFile | None:
        """The export `path` names, or None when its name isn't a Dukascopy export's."""
        path = Path(path)
        match = _NAME.fullmatch(path.name)
        if match is None:
            return None

        end_text = match["end"]
        end = (datetime.strptime(end_text, _DOWNLOAD_TIME_FORMAT) if "T" in end_text
               else datetime.strptime(end_text, _DATE_FORMAT).date())
        return cls(
            path=path,
            instrument=match["instrument"],
            timeframe=match["timeframe"],
            side=PriceSide(match["side"]),
            start=datetime.strptime(match["start"], _DATE_FORMAT).date(),
            end=end,
        )

    def file_name(self) -> str:
        """The name dukascopy-node gives this export; `parse` reads it back."""
        end_format = _DOWNLOAD_TIME_FORMAT if isinstance(self.end, datetime) else _DATE_FORMAT
        return (f"{self.instrument}-{self.timeframe}-{self.side.value}"
                f"-{self.start.strftime(_DATE_FORMAT)}-{self.end.strftime(end_format)}.csv")


@dataclass(frozen=True)
class DukascopyFilePair:
    """The bid and the ask export of one period, side by side in one folder."""

    bid: DukascopyFile
    ask: DukascopyFile
