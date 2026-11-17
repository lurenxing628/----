from __future__ import annotations

from typing import Any, Dict, List

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.seed_results import with_seed_external_group_metadata, with_seed_resource_segments


def coerce_seed_result_item(item: Dict[str, Any]) -> ScheduleResult:
    """The decoder's form of one prepared seed.

    Seeds come from the run's own preparation (freeze window, execution facts, merged external groups),
    whose rows and operations were admitted at their read boundary. Their private transport keys become the
    seed result's own carriers: the merged external group identity, the actual resource segments and the
    point-event witness of a zero-length arrangement.
    """
    result = ScheduleResult(
        op_id=item["op_id"],
        op_code=item["op_code"],
        batch_id=item["batch_id"],
        seq=item["seq"],
        machine_id=item["machine_id"],
        operator_id=item["operator_id"],
        start_time=item["start_time"],
        end_time=item["end_time"],
        source=item["source"],
        op_type_name=item["op_type_name"],
        seed_source=item["seed_source"],
        # Only an execution seed carries the execution state it was built from.
        state_revision=item["state_revision"] if item["seed_source"] == "execution_fact" else None,
        op_type_id=item["op_type_id"],
    )
    if "_external_group_metadata" in item:
        result = with_seed_external_group_metadata(result, item["_external_group_metadata"])
    if "_resource_segments" in item:
        result = with_seed_resource_segments(result, item["_resource_segments"])
    if result.start_time == result.end_time:
        return PointSeedResult(result, item["_point_evidence"])
    return result


def coerce_seed_results(seed_results: List[Dict[str, Any]]) -> List[ScheduleResult]:
    return [coerce_seed_result_item(item) for item in seed_results]
