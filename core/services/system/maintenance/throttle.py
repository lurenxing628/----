from __future__ import annotations

import threading
import time


class MaintenanceThrottle:
    _last_check_ts: float = 0.0
    _check_lock = threading.Lock()

    @classmethod
    def allow_run(cls, throttle_seconds: int) -> bool:
        now_ts = time.time()
        with cls._check_lock:
            if (now_ts - cls._last_check_ts) < int(throttle_seconds):
                return False
            cls._last_check_ts = now_ts
            return True

    @classmethod
    def reset(cls) -> None:
        with cls._check_lock:
            cls._last_check_ts = 0.0

