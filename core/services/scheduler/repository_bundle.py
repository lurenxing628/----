from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.repositories import BatchRepository


@dataclass
class ScheduleRepositoryBundle:
    conn: Any
    logger: Any
    batch_repo: BatchRepository


def build_schedule_repository_bundle(conn: Any, *, logger: Any = None) -> ScheduleRepositoryBundle:
    return ScheduleRepositoryBundle(
        conn=conn,
        logger=logger,
        batch_repo=BatchRepository(conn, logger=logger),
    )
