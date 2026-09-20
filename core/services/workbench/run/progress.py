"""In-process progress ledger for scheduling runs.

The worker thread reports how many candidate plans have finished; the query
path attaches that to a running run. The ledger is deliberately volatile: the
durable record of a run is its receipt, and a restart simply shows no progress
until the worker reports again.
"""

import threading
from typing import Dict, Optional

_LOCK = threading.Lock()
_PROGRESS: Dict[str, Dict[str, object]] = {}


def report_progress(run_ref: str, done: int, total: int, updated_at: str) -> None:
    if not isinstance(done, int) or not isinstance(total, int) or done < 0 or total < 0 or done > total:
        raise ValueError("progress must satisfy 0 <= done <= total")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("progress needs the worker clock reading")
    with _LOCK:
        _PROGRESS[run_ref] = {"done": done, "total": total, "updated_at": updated_at}


def read_progress(run_ref: str) -> Optional[Dict[str, object]]:
    with _LOCK:
        value = _PROGRESS.get(run_ref)
        return dict(value) if value else None


def clear_progress(run_ref: str) -> None:
    with _LOCK:
        _PROGRESS.pop(run_ref, None)
