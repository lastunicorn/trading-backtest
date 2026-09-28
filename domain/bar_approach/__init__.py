"""Domain concepts expressed over streams of `Bar` objects.

Stdlib only, so `ports/` can depend on it without gaining pandas. The DataFrame
counterparts live in `domain.pandas_approach`. This `__init__` imports nothing;
import from the modules directly (`from domain.bar_approach.bar import Bar`).
"""
