from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScheduleRepositoryBundle:
    conn: Any


def build_schedule_repository_bundle(conn: Any) -> ScheduleRepositoryBundle:
    return ScheduleRepositoryBundle(conn=conn)
