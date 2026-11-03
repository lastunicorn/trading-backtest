"""How this repo's MT5 exports differ from what the format alone says.

A headerless 8-column export is ambiguous in the MetaTrader format (TICKVOL
VOL, or TICKVOL SPREAD), so `libs.metatrader_csv` makes the caller choose.
The broker exports this repo works with end in the spread.
"""

from libs.metatrader_csv import FIELDS

__all__ = ["HEADERLESS_LAYOUTS"]

HEADERLESS_LAYOUTS = {8: (*FIELDS[:7], "spread")}
