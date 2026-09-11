"""BarWindow: the collection of at most `count` bars selected from a stream.

    from tools.bar_window import BarWindow

    window = BarWindow(bars, count=20, tail=False)
    for bar in window:      # first iteration reads the source and caches the result
        ...
    for bar in window:      # replays the cached bars; the source isn't touched again
        ...
    window.read_all()       # also reads whatever the source has left, just for the counts
    window.total_count, window.total_visible_count, window.first_bar, ...

Stdlib only.
"""

import itertools
from collections import deque


class BarWindow:
    """The collection of at most `count` bars selected from `bars`.

    Nothing is read from the source until the window is first iterated (or
    `read_all()` is called); that first pass builds and caches the selected
    bars. Every iteration after that replays the cache -- unlike a plain
    generator, a `BarWindow` can be iterated more than once.

    In head mode (`tail=False`) the cache holds the first `count` bars and
    nothing beyond them is ever read from the source, so `total_count`/
    `last_bar`/etc. reflect only what's actually been read. In tail mode the
    last `count` bars are wanted, which can't be known until the source
    ends, so building the cache necessarily reads the whole source; that's
    inherent to the selection, not an extra drain. Either way the cache
    itself is bounded by `count` (a 2.5M-row file costs no more than a
    31k-row one), and `count=None` means "select everything" in both modes.

    `total_count`, `total_visible_count`, `first_bar`, `last_bar`,
    `has_spread` and `has_real_volume` update incrementally as bars are
    read while the cache builds. Call `read_all()` to force a complete read
    of the source (e.g. to get accurate totals in head mode even when
    `count` left the source only partly read).
    """

    def __init__(self, bars, *, count=None, tail=False):
        self._source_bars = bars
        self._requested_count = count
        self._tail = tail
        self._bars = []
        self._built = False

        self.total_count = 0
        self.total_visible_count = 0
        self.first_bar = None
        self.last_bar = None
        self.has_spread = False
        self.has_real_volume = False

    def __iter__(self):
        self._ensure_built()
        return iter(self._bars)

    def read_all(self):
        """Build the window, then read whatever's left of the source purely
        to complete the counts.

        A no-op beyond the build in tail mode, or when `count` is None,
        since those already read the whole source to build the window.
        """
        self._ensure_built()

        for bar in self._source_bars:
            self._observe(bar)

    def _ensure_built(self):
        if self._built:
            return

        select = self._select_tail if self._tail else self._select_head

        for bar in select():
            self._bars.append(bar)

        self._built = True

    def _observe(self, bar):
        self.total_count += 1

        if self.first_bar is None:
            self.first_bar = bar

        self.last_bar = bar

    def _mark_visible(self, bar):
        self.total_visible_count += 1

        if bar.spread is not None:
            self.has_spread = True

        if bar.real_volume:
            self.has_real_volume = True

    def _select_head(self):
        bars = self._source_bars

        if self._requested_count is not None:
            bars = itertools.islice(bars, self._requested_count)

        for bar in bars:
            self._observe(bar)
            self._mark_visible(bar)
            yield bar

    def _select_tail(self):
        buffer = deque(maxlen=self._requested_count)

        for bar in self._source_bars:
            self._observe(bar)
            buffer.append(bar)

        for bar in buffer:
            self._mark_visible(bar)
            yield bar
