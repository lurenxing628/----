"""FIFO admission for costly, independent materialized read snapshots."""

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Condition
from typing import Optional

from core.models.workbench_command import WorkbenchCommandRejected


@dataclass(eq=False)
class _Waiter:
    lane: Optional[str]
    superseded: bool = False


class ReadBudget:
    def __init__(self, capacity):
        self._available = capacity
        self._condition = Condition()
        self._waiting = deque()

    @contextmanager
    def slot(self, lane: Optional[str] = None):
        ticket = _Waiter(lane)
        with self._condition:
            if lane and self._waiting:
                remaining = deque()
                for waiter in self._waiting:
                    if waiter.lane == lane:
                        waiter.superseded = True
                    else:
                        remaining.append(waiter)
                self._waiting = remaining
            self._waiting.append(ticket)
            self._condition.notify_all()
            try:
                while not ticket.superseded and (self._waiting[0] is not ticket or not self._available):
                    self._condition.wait()
                if ticket.superseded:
                    raise WorkbenchCommandRejected("request_superseded", "筛选条件已更新，前一次读取已取消。", 499)
                self._waiting.popleft()
                self._available -= 1
            except BaseException:
                if not ticket.superseded:
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


# Plan-derived views (dashboard, field tasks) queue on their own bounded slot pool:
# bounded concurrency keeps short read transactions from stretching under GIL contention.
PLAN_READ_SLOTS = ReadBudget(2)
