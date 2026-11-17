from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence, Tuple

from core.shared.local_datetime import datetime_to_us, us_to_iso

from .base_repo import BaseRepository

# An arrangement's time columns, shared by Schedule and WorkbenchRunCandidateTasks.
STORED_INSTANT_COLUMNS = ("start_time", "end_time", "start_us", "end_us", "is_point_event")


def stored_instants(start: datetime, end: datetime) -> Tuple[str, str, int, int, int]:
    """The time columns of one arrangement, in ``STORED_INSTANT_COLUMNS`` order.

    The microseconds are the instant; the display text is generated from them by ``us_to_iso`` and
    a point event is an arrangement whose start and end coincide.
    """
    start_us, end_us = datetime_to_us(start), datetime_to_us(end)
    return us_to_iso(start_us), us_to_iso(end_us), start_us, end_us, int(start_us == end_us)


_ARRANGEMENT_COLUMNS = (
    "version",
    "task_ref",
    "op_id",
    "operation_ref",
    "batch_id",
    "batch_priority",
    "piece_id",
    "seq",
    "op_type_name",
    "op_type_ref",
    "op_type_label",
    "source",
    "setup_hours",
    "unit_hours",
    "quantity",
    "remaining_quantity",
    "batch_quantity",
    "quantity_basis",
    "quantity_reason",
    "machine_id",
    "machine_ref",
    "machine_label",
    "operator_id",
    "operator_ref",
    "operator_label",
    "supplier_id",
    "supplier_ref",
    "supplier_label",
    "lock_status",
)

_INSERT_COLUMNS = _ARRANGEMENT_COLUMNS + STORED_INSTANT_COLUMNS

_INSERT_SQL = (
    "INSERT INTO Schedule ("
    + ", ".join(_INSERT_COLUMNS)
    + ") VALUES ("
    + ", ".join("?" for _ in _INSERT_COLUMNS)
    + ")"
)


class ScheduleRepository(BaseRepository):
    """排程结果仓库（Schedule）。"""

    def bulk_create(self, schedules: Sequence[Mapping[str, Any]]) -> int:
        """每条安排的 ``start_time``/``end_time`` 是 datetime；时间列由 ``stored_instants`` 一处生成。"""
        return self.executemany(
            _INSERT_SQL,
            (
                tuple(item[col] for col in _ARRANGEMENT_COLUMNS) + stored_instants(item["start_time"], item["end_time"])
                for item in schedules
            ),
        ).rowcount
