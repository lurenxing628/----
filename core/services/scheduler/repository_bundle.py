from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.repositories import (
    BatchOperationRepository,
    BatchRepository,
    ScheduleHistoryRepository,
    ScheduleRepository,
)


@dataclass
class ScheduleRepositoryBundle:
    conn: Any
    logger: Any
    batch_repo: BatchRepository
    op_repo: BatchOperationRepository
    schedule_repo: ScheduleRepository
    history_repo: ScheduleHistoryRepository


def build_schedule_repository_bundle(conn: Any, *, logger: Any = None) -> ScheduleRepositoryBundle:
    return ScheduleRepositoryBundle(
        conn=conn,
        logger=logger,
        batch_repo=BatchRepository(conn, logger=logger),
        op_repo=BatchOperationRepository(conn, logger=logger),
        schedule_repo=ScheduleRepository(conn, logger=logger),
        history_repo=ScheduleHistoryRepository(conn, logger=logger),
    )
