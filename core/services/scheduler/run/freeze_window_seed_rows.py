"""Validate and materialize frozen prefixes without changing their identities."""

from types import SimpleNamespace
from typing import Any, Dict, List, Set

from core.algorithm_contracts.schedule_point_evidence import verified_point
from core.algorithms.value_domains import INTERNAL


def cache_seed_for_prefix(svc, *, prefix, schedule_map, seed_tmp, point_validator=None):
    for oid in prefix:
        row = schedule_map.get(int(oid)) or {}
        start = svc._normalize_datetime(row.get("start_time"))
        end = svc._normalize_datetime(row.get("end_time"))
        if not start or not end or end < start:
            return int(oid)
        if start == end:
            parsed = SimpleNamespace(**dict(row, source=INTERNAL, start_time=start, end_time=end))
            if not verified_point(parsed, point_validator):
                return int(oid)
        seed_tmp[int(oid)] = {"row": row, "start_time": start, "end_time": end}
    return 0


def discard_seed_cache(prefix, seed_tmp):
    for oid in prefix:
        seed_tmp.pop(int(oid), None)


def build_seed_results(frozen_op_ids: Set[int], *, op_by_id: Dict[int, Any],
                       seed_tmp: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for oid in sorted(frozen_op_ids):
        op, seed = op_by_id.get(oid), seed_tmp.get(oid)
        if not op or not seed:
            continue
        row, start, end = seed.get("row"), seed.get("start_time"), seed.get("end_time")
        if not row or not start or not end:
            continue
        results.append({"op_id": oid, "op_code": op.op_code, "batch_id": op.batch_id,
                        "seq": int(op.seq or 0), "machine_id": row.get("machine_id"),
                        "operator_id": row.get("operator_id"), "start_time": start, "end_time": end,
                        "source": (op.source or INTERNAL).strip(), "op_type_name": getattr(op, "op_type_name", None)})
    return results
