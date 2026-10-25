"""Validate and materialize frozen prefixes without changing their identities."""

from typing import Any, Dict, List, Set

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL
from core.shared.local_datetime import parse_local_datetime as parse_dt


def cache_seed_for_prefix(*, prefix, schedule_map, op_by_id, seed_tmp, point_validator):
    """零工时点事件按最终 seed 的来源口径取一次见证，随 seed 一起保存，下游直接使用。"""
    for oid in prefix:
        row = schedule_map[int(oid)]
        parsed_times = row.get("_parsed_times")
        start, end = parsed_times if parsed_times is not None else (parse_dt(row.get("start_time")), parse_dt(row.get("end_time")))
        if not start or not end or end < start:
            return int(oid)
        seed = {"row": row, "start_time": start, "end_time": end}
        if start == end:
            op = op_by_id[int(oid)]
            # 见证按存储行原样的编号与资源比对；工序号只作展示，见证不读它。
            parsed = ScheduleResult(op_id=row["op_id"], op_code=op.op_code, batch_id=op.batch_id, seq=op.seq,
                                    machine_id=row["machine_id"], operator_id=row["operator_id"],
                                    start_time=start, end_time=end, source=(op.source or INTERNAL).strip())
            evidence = point_validator(parsed)
            if type(evidence) is not SchedulePointEvidence or not evidence.matches(parsed):
                return int(oid)
            seed["point_evidence"] = evidence
        seed_tmp[int(oid)] = seed
    return 0


def build_seed_results(frozen_op_ids: Set[int], *, op_by_id: Dict[int, Any],
                       seed_tmp: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for oid in frozen_op_ids:
        op, seed = op_by_id[oid], seed_tmp[oid]
        row, start, end = seed["row"], seed["start_time"], seed["end_time"]
        result = {"op_id": oid, "op_code": op.op_code, "batch_id": op.batch_id,
                  "seq": int(op.seq or 0), "machine_id": row.get("machine_id"),
                  "operator_id": row.get("operator_id"), "start_time": start, "end_time": end,
                  "source": (op.source or INTERNAL).strip(), "op_type_name": op.op_type_name,
                  "op_type_id": op.op_type_id, "seed_source": "freeze_window"}
        if start == end:
            result["_point_evidence"] = seed["point_evidence"]
        results.append(result)
    results.sort(key=lambda x: (x["start_time"], x["op_id"]))
    return results
