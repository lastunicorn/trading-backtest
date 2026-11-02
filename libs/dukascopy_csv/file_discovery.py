"""Finding Dukascopy exports on disk and matching each bid file with its ask file.

Only file names are looked at; nothing is read. Files are recognised by name
alone, so any folder layout works (flat, or grouped by instrument and year).
"""

from __future__ import annotations

from pathlib import Path

from .dukascopy_file import DukascopyFile, DukascopyFilePair, PriceSide

__all__ = ["find_files", "find_pair", "pair_files"]


def find_files(path: str | Path) -> list[DukascopyFile]:
    """Every Dukascopy export under folder `path` (searched recursively), or the one export `path` is.

    Files whose names aren't Dukascopy exports (notes, other CSVs) are skipped
    in a folder; an empty list means none were found. Sorted by instrument,
    timeframe, start date, then side, which is calendar order per instrument.

    Raises FileNotFoundError if `path` doesn't exist, ValueError if `path` is
    a file not named like a Dukascopy export.
    """
    path = Path(path)
    if path.is_file():
        return [_parse_or_raise(path)]
    if not path.is_dir():
        raise FileNotFoundError(f"no Dukascopy export at {path}")

    files = (DukascopyFile.parse(candidate) for candidate in path.rglob("*.csv"))
    return sorted((file for file in files if file is not None), key=_order)


def pair_files(files: list[DukascopyFile]) -> list[DukascopyFilePair]:
    """Match each bid file with its ask file.

    Partners sit in the same folder and share the instrument, timeframe and
    start date. Their end may differ: a partial download's end is the
    download time, which is rarely the same for both sides. Sorted like
    `find_files`.

    Raises FileNotFoundError if a file has no partner, ValueError if one
    period has two files for the same side.
    """
    sides: dict[tuple, dict[PriceSide, DukascopyFile]] = {}
    for file in files:
        pair = sides.setdefault(_pair_key(file), {})
        if file.side in pair:
            raise ValueError(f"two Dukascopy {file.side.value} files for one period: "
                             f"{pair[file.side].path} and {file.path}")
        pair[file.side] = file

    incomplete = [next(iter(pair.values())).path for pair in sides.values() if len(pair) != 2]
    if incomplete:
        raise FileNotFoundError("Dukascopy file(s) without the other side of their pair: "
                                + ", ".join(map(str, incomplete)))

    pairs = (DukascopyFilePair(bid=pair[PriceSide.BID], ask=pair[PriceSide.ASK]) for pair in sides.values())
    return sorted(pairs, key=lambda pair: _order(pair.bid))


def find_pair(path: str | Path) -> DukascopyFilePair:
    """The pair the export at `path` belongs to: `path` itself plus its partner in the same folder.

    Raises FileNotFoundError if `path` or its partner is missing, ValueError
    if `path` isn't named like a Dukascopy export.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no Dukascopy export at {path}")
    file = _parse_or_raise(path)

    siblings = (DukascopyFile.parse(candidate) for candidate in path.parent.glob("*.csv"))
    [pair] = pair_files([sibling for sibling in siblings
                         if sibling is not None and _pair_key(sibling) == _pair_key(file)])
    return pair


def _parse_or_raise(path: Path) -> DukascopyFile:
    file = DukascopyFile.parse(path)
    if file is None:
        raise ValueError(f"{path} is not a Dukascopy export: expected a name like "
                         "eurusd-m1-bid-2020-01-01-2020-02-01.csv")
    return file


def _pair_key(file: DukascopyFile) -> tuple:
    return file.path.parent, file.instrument, file.timeframe, file.start


def _order(file: DukascopyFile) -> tuple:
    return file.instrument, file.timeframe, file.start, file.side.value, str(file.path)
