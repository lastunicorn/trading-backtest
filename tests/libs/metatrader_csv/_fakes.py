"""Export files shared by the library's tests."""

from pathlib import Path

REAL_ARCHIVE = Path("/nfs/YubabaFinance/trading/historical data")

HEADERLESS_7 = (
    "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    "2020.01.02,00:01,1.15,1.25,1.1,1.2,\n"
)

MT5_HEADER_9 = (
    "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    "2026.07.01\t00:00:00\t1.1\t1.2\t1.0\t1.15\t17\t0\t20\n"
    "2026.07.01\t00:01:00\t1.1\t1.2\t1.0\t1.15\t14.0\t5\t\n"
)

HEADERLESS_8 = (
    "2020.01.02;00:00;1.1;1.2;1.0;1.15;10;7\n"
    "2020.01.02;00:01;1.1;1.2;1.0;1.15;10;8\n"
)

EIGHTH_IS_SPREAD = {8: ("date", "time", "open", "high", "low", "close", "tick_volume", "spread")}
EIGHTH_IS_VOLUME = {8: ("date", "time", "open", "high", "low", "close", "tick_volume", "volume")}

WITH_BAD_ROW = (
    "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    "\n"
    "2020.01.02,00:02,bad,1.2,1.0,1.1,3\n"
    "2020.01.02,00:03,1.1,1.2,1.0,1.1,4\n"
)


def write_csv(folder: Path, text: str, name: str = "export.csv") -> Path:
    path = folder / name
    path.write_text(text)
    return path


def real_exports() -> list[Path]:
    """One export of each shape in the local archive (empty when it isn't mounted).

    Headerless comma M1 and M5 (arty), tab-separated with an MT5 header and
    seconds (arty "1min - mt5"), and histdata.com's MT download.
    """
    folders = [REAL_ARCHIVE / "arty" / "eurusd" / name for name in ("1min", "1min - mt5", "5min")]
    folders.append(REAL_ARCHIVE / "histdata" / "mt" / "2025")
    return [min(folder.glob("*.csv")) for folder in folders if folder.is_dir() and any(folder.glob("*.csv"))]
