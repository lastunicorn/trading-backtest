"""Builders for the `trading_sessions.py` tests: tiny headerless MT5 exports."""

from pathlib import Path


def export(path: Path, bars: list[tuple[str, float]]) -> Path:
    """Write an M1 export with one bar per `("YYYY.MM.DD HH:MM", price)`.

    Each bar is open = `price`, high = `price` + 0.001, low = `price` - 0.001,
    close = `price` + 0.0005, so a session's open/close/high/low say which
    bars it took.
    """
    lines = []
    for stamp, price in bars:
        day, clock = stamp.split()
        lines.append(f"{day},{clock},{price:.5f},{price + 0.001:.5f},{price - 0.001:.5f},{price + 0.0005:.5f},10")
    path.write_text("\n".join(lines) + "\n")
    return path
