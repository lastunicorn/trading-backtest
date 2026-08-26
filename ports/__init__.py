"""Reusable I/O building blocks, kept outside the numbered research pipeline.

The `eurusd_*_vNN.py` scripts are immutable, self-contained research stages.
Anything in here is the opposite: shared, stdlib-only code that new tooling can
import without pulling in pandas or depending on a research stage.

A port knows a file format and nothing else -- it parses one record into one
typed object and stops. What the data then becomes (cleaned, deduplicated,
resampled) is `domain/`'s job.
"""
