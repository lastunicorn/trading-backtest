"""Technical indicators computed from a bar frame: the RSI, the divergences
between an oscillator and price, and the entry signals those divergences give.

Pure calculations over pandas Series/DataFrames, grouped as in
`doc/architecture/domain/indicators.md`. This `__init__` imports nothing;
import from the modules directly (`from domain.indicators.rsi import rsi`).
"""
