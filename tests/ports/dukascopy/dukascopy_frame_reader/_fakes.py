"""Builders for Dukascopy export files, shared by the reader's tests."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _epoch_ms(text: str) -> int:
    return int(datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)


def write_side(
    data_dir: Path, folder_year: int, side: str, year: int, month: int, rows: dict[str, tuple]
) -> None:
    end_year, end_month = (year, month + 1) if month < 12 else (year + 1, 1)
    name = f"eurusd-m1-{side}-{year:04d}-{month:02d}-01-{end_year:04d}-{end_month:02d}-01.csv"
    folder = data_dir / f"{folder_year:04d}"
    folder.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(
        {
            "timestamp": [_epoch_ms(stamp) for stamp in rows],
            "open": [values[0] for values in rows.values()],
            "high": [values[1] for values in rows.values()],
            "low": [values[2] for values in rows.values()],
            "close": [values[3] for values in rows.values()],
        }
    )
    frame.to_csv(folder / name, index=False)
