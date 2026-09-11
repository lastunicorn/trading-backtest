"""Show only `count` bars from a stream, while still accounting for all of it.

    from tools.bar_scan import BarScan

    scan = BarScan(bars, count=20, tail=False)
    displayed = list(scan)
    scan.total, scan.total_visible, scan.first, scan.last, scan.has_spread, ...

Stdlib only.
"""

from collections import deque


class BarScan:
    """Iterator[Bar] over `bars` that shows only `count` of them.

    In head mode (`tail=False`) the first `count` bars are yielded as they
    arrive and the rest of the source is drained -- unyielded -- to keep
    `total` and `last` accurate; that drain happens on the final `next()`
    call. In tail mode the last `count` bars are wanted, which can't be known
    until the source ends, so the whole source is drained up front on the
    *first* `next()` call, buffered in a `deque(maxlen=count)`, and then
    yielded. Either way memory is bounded by `count` (a 2.5M-row file costs no
    more than a 31k-row one), and `count=None` means "yield everything" in
    both modes.

    Like any generator-backed iterator this is single-pass: iterate it once.
    """

    def __init__(self, bars, *, count=None, tail=False):
        self._bars = bars
        self._count = count
        self._tail = tail

        self.total = 0
        self.total_visible = 0
        self.first = None
        self.last = None
        self.has_spread = False
        self.has_real_volume = False

    def __iter__(self):
        return self._iter_tail() if self._tail else self._iter_head()

    def _observe(self, bar):
        self.total += 1

        if self.first is None:
            self.first = bar

        self.last = bar

    def _mark_visible(self, bar):
        self.total_visible += 1

        if bar.spread is not None:
            self.has_spread = True

        if bar.real_volume:
            self.has_real_volume = True

    def _iter_head(self):
        for bar in self._bars:
            self._observe(bar)

            if self._count is None or self.total_visible < self._count:
                self._mark_visible(bar)
                yield bar

    def _iter_tail(self):
        buffer = deque(maxlen=self._count)

        for bar in self._bars:
            self._observe(bar)
            buffer.append(bar)

        for bar in buffer:
            self._mark_visible(bar)
            yield bar
