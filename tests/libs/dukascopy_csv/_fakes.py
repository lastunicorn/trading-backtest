"""Builders for Dukascopy export files, shared by the library's tests."""

from datetime import datetime, timezone
from pathlib import Path


def epoch_ms(text: str) -> int:
    """`"2020-01-01 00:00"` (UTC) as epoch milliseconds, the way Dukascopy stores it."""
    return int(datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)


def write_export(folder: Path, name: str, rows: dict[str, tuple] | None = None,
                 header: str = "timestamp,open,high,low,close") -> Path:
    """Write `folder/name` with `header` and one line per `rows` item (stamp -> the other values)."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = [header] + [",".join(map(str, (epoch_ms(stamp), *values))) for stamp, values in (rows or {}).items()]
    path = folder / name
    path.write_text("\n".join(lines) + "\n")
    return path


def write_pair(folder: Path, instrument: str = "eurusd", start: str = "2020-01-01",
               end: str = "2020-02-01") -> tuple[Path, Path]:
    """An empty bid and ask export of one period; returns (bid, ask)."""
    return tuple(write_export(folder, f"{instrument}-m1-{side}-{start}-{end}.csv") for side in ("bid", "ask"))
