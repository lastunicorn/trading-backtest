"""argparse `type=` converters shared by the entry scripts.

    from ui.cli_args import timezone_arg

    parser.add_argument("--timezone", type=timezone_arg, default=None, metavar="TZ")
    args.timezone          # a tzinfo (or the default), never the raw string

A bad value becomes an ordinary argparse usage error ("argument --timezone:
..."), so a script never has to check the parsed value itself.

Stdlib + `domain` only.
"""

import argparse
from datetime import tzinfo
from zoneinfo import ZoneInfoNotFoundError

from domain.broker_clock import BROKER_TZ_NAME, timezone_by_name


def timezone_arg(name: str) -> tzinfo:
    """`timezone_by_name(name)`: `BROKER_SERVER_TZ` for "broker", otherwise an IANA zone.

    Raises `argparse.ArgumentTypeError` for a name that isn't a zone --
    unknown (`ZoneInfoNotFoundError`) or malformed, such as an empty or
    absolute path (`ValueError`).
    """
    try:
        return timezone_by_name(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise argparse.ArgumentTypeError(
            f"unknown timezone {name!r}: expected {BROKER_TZ_NAME!r} or an IANA name "
            f"such as 'UTC' or 'Europe/London'") from None
