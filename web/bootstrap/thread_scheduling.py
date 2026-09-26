"""Bound CPython 3.8's GIL handoff delay while the Windows server is serving."""

import os
import sys
import threading
from contextlib import contextmanager

_LOCK = threading.Lock()
_OWNERS = 0
_PREVIOUS = 0.005
_APPLIED = 0.005
_INTERVAL = 0.0001


@contextmanager
def responsive_thread_scheduling():
    """Avoid SQLite's per-row GIL convoy behind the CPU-bound scheduler.

    A 5 ms handoff can turn a subsecond batch read into tens of seconds on
    Windows/Python 3.8. This changes interpreter scheduling, never HTTP deadlines,
    SQL transactions, or the algorithm. Retain a caller's shorter interval and
    restore our process setting only after the last serving owner exits.
    """
    global _OWNERS, _PREVIOUS, _APPLIED
    if os.name != "nt" or sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 8):
        yield
        return
    with _LOCK:
        if not _OWNERS:
            _PREVIOUS = sys.getswitchinterval()
            _APPLIED = min(_PREVIOUS, _INTERVAL)
            sys.setswitchinterval(_APPLIED)
            _APPLIED = sys.getswitchinterval()
        _OWNERS += 1
    try:
        yield
    finally:
        with _LOCK:
            _OWNERS -= 1
            if not _OWNERS:
                # Do not overwrite an explicit setting made by another owner.
                if sys.getswitchinterval() == _APPLIED:
                    sys.setswitchinterval(_PREVIOUS)
