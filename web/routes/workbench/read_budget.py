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
