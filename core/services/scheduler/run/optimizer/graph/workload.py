"""Operation-local workload and precedence release estimates for graph features."""
from __future__ import annotations

import heapq
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, NoReturn, Optional, Set, Tuple

from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.algorithm_runtime.piece_input import external_group_key
from core.errors import ValidationError
from core.shared.strict_parse import parse_optional_date


def operation_workload_signals(
    operations: Dict[int, Any], *, batches: Dict[str, Any],
    start_dt: datetime, graph_ready_context: Any,
    seed_results: List[Any], calendar_service: Any, work_buckets: Any,
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """Count each reachable work bucket once; release follows longest predecessor path.

    These are gross precedence estimates, not a resource-feasible schedule. Fixed
    predecessors with seed evidence use their completion; other fixed work is
    already completed under the graph dispatch contract.
    """
    buckets, members, work = work_buckets
    links, release = _bucket_releases(
        operations, batches, buckets, graph_ready_context["predecessor_op_ids_by_op_id"], start_dt, seed_results,
    )
    ordered = _topological_order(links)
    _advance_releases(operations, batches, members, work, links, release, ordered, calendar_service)
    burden = _remaining_burdens(work, links, ordered)
    return ({op_id: burden[bucket] for op_id, bucket in buckets.items()},
            {op_id: (release[bucket] - start_dt).total_seconds() / 3600.0 for op_id, bucket in buckets.items()})


def batch_ordering_workload_signals(operations, durations, *, work_buckets):
    """Retain the established whole-batch ordering heuristic, using real work units.

    This is a candidate ordering signal, not a precedence release estimate. Piece
    quantities and external-group identities retain the current input contract.
    """
    buckets, _members, work = work_buckets
    by_batch: Dict[str, List[int]] = {}
    for op_id in durations:
        by_batch.setdefault(str(operations[op_id].batch_id), []).append(op_id)
    remaining, offsets = {}, {}
    for ids in by_batch.values():
        ordered_buckets = dict.fromkeys(buckets[op_id] for op_id in sorted(ids))
        total = sum(work[bucket] for bucket in ordered_buckets)
        elapsed = 0.0
        starts = {}
        for op_id in sorted(ids, key=lambda key: (int(operations[key].seq or key), key)):
            bucket = buckets[op_id]
            if bucket not in starts:
                starts[bucket] = elapsed
                elapsed += work[bucket]
            offsets[op_id] = starts[bucket]
        for op_id in ids:
            remaining[op_id] = total
    return remaining, offsets


def build_work_buckets(operations, durations):
    buckets = {op_id: _work_bucket(operations[op_id], op_id) for op_id in durations}
    members: Dict[Tuple[str, ...], List[int]] = {}
    for op_id, bucket in buckets.items():
        members.setdefault(bucket, []).append(op_id)
    work = {}
    for bucket, ids in members.items():
        values = {durations[op_id] for op_id in ids}
        if len(values) != 1:
            _invalid("同一合并外协组的总工时不一致。")
        work[bucket] = values.pop()
    return buckets, members, work


def _bucket_releases(
    operations: Dict[int, Any], batches: Dict[str, Any], buckets: Dict[int, Tuple[str, ...]],
    predecessors: Dict[int, Set[int]], start_dt: datetime, seed_results: List[Any],
) -> Tuple[Dict[Tuple[str, ...], Set[Tuple[str, ...]]], Dict[Tuple[str, ...], datetime]]:
    links: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = {bucket: set() for bucket in buckets.values()}
    release = {bucket: start_dt for bucket in links}
    seed_ends = {int(item.op_id): item.end_time for item in seed_results
                 if isinstance(item.end_time, datetime)}
    ready_by_batch: Dict[str, Optional[datetime]] = {}
    for op_id, bucket in buckets.items():
        batch_id = str(operations[op_id].batch_id)
        if batch_id not in ready_by_batch:
            ready = parse_optional_date(batches[batch_id].ready_date, field="ready_date")
            ready_by_batch[batch_id] = None if ready is None else datetime.combine(ready, datetime.min.time())
        ready_dt = ready_by_batch[batch_id]
        if ready_dt is not None:
            release[bucket] = max(release[bucket], ready_dt)
        for parent in predecessors[op_id]:
            if parent in buckets and buckets[parent] != bucket:
                links[buckets[parent]].add(bucket)
            elif parent not in buckets:
                release[bucket] = max(release[bucket], seed_ends.get(parent, start_dt))
    return links, release


def _advance_releases(operations, batches, members, work, links, release, ordered, calendar_service):
    for bucket in ordered:
        if not links[bucket]:
            continue
        op = operations[members[bucket][0]]
        finish = _gross_finish(op, batches[str(op.batch_id)], release[bucket], work[bucket], calendar_service)
        for child in links[bucket]:
            release[child] = max(release[child], finish)


def _remaining_burdens(work, links, ordered):
    # Python integer bitsets avoid copying a descendant set per operation.
    indexes = {bucket: index for index, bucket in enumerate(ordered)}
    reachable = {}
    burden = {}
    for bucket in reversed(ordered):
        bits = 1 << indexes[bucket]
        for child in links[bucket]:
            bits |= reachable[child]
        reachable[bucket] = bits
        if len(links[bucket]) == 1:
            total = work[bucket] + burden[next(iter(links[bucket]))]
        else:
            total = 0.0
            while bits:
                low = bits & -bits
                total += work[ordered[low.bit_length() - 1]]
                bits ^= low
        if not math.isfinite(total):
            _invalid("工序及后继的剩余工时必须为有限数字。")
        burden[bucket] = total
    return burden


def _work_bucket(op: Any, op_id: int) -> Tuple[str, ...]:
    # 排产输入构建保证合并外协组必带组身份。
    if op.source == EXTERNAL and op.ext_merge_mode == MERGED:
        return ("external",) + external_group_key(op)
    return ("operation", str(op_id))


def _topological_order(links):
    counts = {key: 0 for key in links}
    for children in links.values():
        for child in children:
            counts[child] += 1
    ready = [key for key, count in counts.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        key = heapq.heappop(ready)
        ordered.append(key)
        for child in links[key]:
            counts[child] -= 1
            if counts[child] == 0:
                heapq.heappush(ready, child)
    if len(ordered) != len(links):
        _invalid("工序特征前置关系包含环。")
    return ordered


def _gross_finish(op: Any, batch: Any, start: datetime, hours: float, calendar: Any) -> datetime:
    if op.source == EXTERNAL:
        return start + timedelta(hours=hours)
    finish = calendar.add_working_hours(start, hours, priority=batch.priority, operator_id=op.operator_id)
    if not isinstance(finish, datetime) or finish < start:
        _invalid("日历返回无效的工序完成时间。")
    return finish


def _invalid(message: str) -> NoReturn:
    raise ValidationError(message, field="graph_ready_v2_features",
                          details={"reason": "graph_ready_bad_v2_workload"})
