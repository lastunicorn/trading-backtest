"""Builders for MT5 export files, shared by this directory's tests."""

from pathlib import Path

HEADERLESS_7 = (
    "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    "2020.01.02,00:01,1.15,1.25,1.1,1.2,\n"
)

MT5_HEADER_9 = (
    "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    "2026.07.01\t00:00:00\t1.1\t1.2\t1.0\t1.15\t17\t0\t20\n"
    "2026.07.01\t00:01:00\t1.1\t1.2\t1.0\t1.15\t14\t5\t\n"
)

SEMICOLON_8 = (
    "2020.01.02;00:00;1.1;1.2;1.0;1.15;10;7\n"
    "2020.01.02;00:01;1.1;1.2;1.0;1.15;10;8\n"
)

WITH_BAD_ROW = (
    "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    "\n"
    "2020.01.02,00:02,bad,1.2,1.0,1.1,3\n"
    "2020.01.02,00:03,1.1,1.2,1.0,1.1,4.0\n"
)


def write_csv(folder: Path, text: str, name: str = "export.csv") -> Path:
    path = folder / name
    path.write_text(text)
    return path
