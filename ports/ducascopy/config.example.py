"""Template for `config.py` -- the local path to the Dukascopy export folder.

`config.py` itself is gitignored: the export folder lives outside the repo and
its path is specific to this machine. Copy this file to `config.py` (same
directory) and point `DATA_DIR` at it:

    cp ports/ducascopy/config.example.py ports/ducascopy/config.py

`DATA_DIR` is the folder that directly contains the year subfolders
(`2020/`, `2021/`, ...), each holding `eurusd-m1-bid-*.csv` /
`eurusd-m1-ask-*.csv` pairs.
"""

from pathlib import Path

DATA_DIR = Path("/path/to/ducascopy/eurusd")
