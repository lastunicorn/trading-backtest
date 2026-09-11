"""Show only `count` bars from a stream, while tracking what's been read.

    from tools.bar_window import BarWindow

    window = BarWindow(bars, count=20, tail=False)
    displayed = window.read_all()
    window.total_count, window.total_visible_count, window.first_bar, ...

Stdlib only.
"""

import itertools
from collections import deque


class BarWindow:
    """Iterator[Bar] over `bars` that shows only `count` of them.

    In head mode (`tail=False`) iteration stops as soon as `count` bars have
    been yielded -- nothing beyond that is read from the source, so
    `total_count`/`last_bar`/etc. reflect only what's actually been read, not
    the whole stream. In tail mode the last `count` bars are wanted, which
    can't be known until the source ends, so iteration necessarily reads the
    whole source before yielding anything; that's inherent to the selection,
    not an extra drain. Either way memory is bounded by `count` (a 2.5M-row
    file costs no more than a 31k-row one), and `count=None` means "yield
    everything" in both modes.

    `total_count`, `total_visible_count`, `first_bar`, `last_bar`,
    `has_spread` and `has_real_volume` update incrementally as bars are
    pulled through iteration -- they never trigger reads on their own. Call
    `read_all()` to force a complete read (e.g. to get accurate totals in
    head mode even when `count` cut iteration short).

    Like any generator-backed iterator this is single-pass: exhausting it
    once exhausts the underlying source for good.
    """

    def __init__(self, bars, *, count=None, tail=False):
        self._source_bars = bars
        self._requested_count = count
        self._tail = tail

        self.total_count = 0
        self.total_visible_count = 0
        self.first_bar = None
        self.last_bar = None
        self.has_spread = False
        self.has_real_volume = False

    def __iter__(self):
        return self._iter_tail() if self._tail else self._iter_head()

    def read_all(self):
        """Read everything -- the displayed bars plus whatever iteration would
        otherwise leave unread -- and return the displayed bars.

        A no-op drain beyond normal iteration in tail mode, or when `count`
        is None, since those already read the whole source to produce
        anything.
        """
        displayed = list(self)

        for bar in self._source_bars:
            self._observe(bar)

        return displayed

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

    def _iter_head(self):
        bars = self._source_bars

        if self._requested_count is not None:
            bars = itertools.islice(bars, self._requested_count)

        for bar in bars:
            self._observe(bar)
            self._mark_visible(bar)
            yield bar

    def _iter_tail(self):
        buffer = deque(maxlen=self._requested_count)

        for bar in self._source_bars:
            self._observe(bar)
            buffer.append(bar)

        for bar in buffer:
            self._mark_visible(bar)
            yield bar
