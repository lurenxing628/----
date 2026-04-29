from __future__ import annotations

from typing import List, Optional, get_type_hints

from data.repositories.schedule_repo import ScheduleRepository
from data.repositories.schedule_rows import (
    ScheduleDetailRow,
    ScheduleDispatchRow,
    ScheduleSeedRow,
    ScheduleTimeSpanRow,
)


def test_schedule_repository_dict_rows_have_named_return_contracts() -> None:
    assert get_type_hints(ScheduleRepository.get_version_time_span)["return"] == Optional[ScheduleTimeSpanRow]
    assert (
        get_type_hints(ScheduleRepository.list_version_rows_by_op_ids_start_range)["return"]
        == List[ScheduleSeedRow]
    )
    assert get_type_hints(ScheduleRepository.list_overlapping_with_details)["return"] == List[ScheduleDetailRow]
    assert get_type_hints(ScheduleRepository.list_by_version_with_details)["return"] == List[ScheduleDetailRow]
    assert (
        get_type_hints(ScheduleRepository.list_dispatch_rows_with_resource_context)["return"]
        == List[ScheduleDispatchRow]
    )
