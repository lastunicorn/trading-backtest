"""Reusable I/O building blocks, kept outside the numbered research pipeline.

The `eurusd_*_vNN.py` scripts are immutable, self-contained research stages.
Anything in here is the opposite: shared, stdlib-only code that new tooling can
import without pulling in pandas or depending on a research stage.
"""
