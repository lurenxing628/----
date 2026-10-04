"""FIFO admission for costly, independent materialized read snapshots."""

from collections import deque
from contextlib import contextmanager
from threading import Condition


class ReadBudget:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("Read capacity must be positive")
        self._available = capacity
        self._condition = Condition()
        self._waiting = deque()

    @contextmanager
    def slot(self):
        ticket = object()
        with self._condition:
            self._waiting.append(ticket)
            self._condition.notify_all()
            try:
                while self._waiting[0] is not ticket or not self._available:
                    self._condition.wait()
                self._waiting.popleft()
                self._available -= 1
            except BaseException:
                self._waiting.remove(ticket)
                self._condition.notify_all()
                raise
            self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                self._available += 1
                self._condition.notify_all()


# Each batch view projects the complete ledger, even for a short page, one preview or
# one file. One reader avoids per-row SQLite/GIL handoff contention between large scans;
# every batch read route, list and file routes alike, queues on this single slot.
BATCH_READ_SLOTS = ReadBudget(1)

# Plan-derived views (dashboard, field tasks) each rebuild the whole current official
# plan and its ledger for any page. They queue on their own single slot: one such
# rebuild at a time keeps its short read transaction from stretching under GIL
# contention, while batch pages never wait behind a dashboard (or the reverse).
PLAN_READ_SLOTS = ReadBudget(1)


@contextmanager
def batch_read_snapshot(reader, *, detached=True):
    # FIFO waiters hold no SQLite transaction and cannot starve behind newcomers.
    with BATCH_READ_SLOTS.slot():
        context = reader.detached_read_snapshot() if detached else reader.read_snapshot()
        with context as fingerprint:
            yield fingerprint
