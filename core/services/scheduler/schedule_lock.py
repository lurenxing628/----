"""One process-local lock for scheduling, adoption and host recovery."""

from threading import Lock

RUN_SCHEDULE_LOCK = Lock()
