"""Bind one complete split scope before resource selection or computation."""

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.run.schedule_input_seed_metadata import protected_interval_problem
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.run_input_rows import fail


def input_piece_scope(operations, batches):
    if not any(op.piece_id is not None for op in operations):
        return None
    try:
        scope = build_piece_adoption_scope(operations, batches)
    except PieceAdoptionBlocked as exc:
        fail(exc.code, str(exc), batch_id=exc.batch_id)
    return scope


def _reduce_seeded_ancestors(ancestors, seeds, groups):
    latest_unmerged = None
    by_group = {}
    for ancestor in ancestors:
        group = groups[ancestor]
        seed = seeds[ancestor]
        if group is None:
            if latest_unmerged is None or seed["end_time"] >= seeds[latest_unmerged]["end_time"]:
                latest_unmerged = ancestor
            continue
        entry = by_group.get(group)
        if entry is None:
            by_group[group] = [ancestor, ancestor, None]
            continue
        first, latest, split = entry
        if seed["end_time"] > seeds[latest]["end_time"]:
            entry[1] = ancestor
        if split is None and (seed["start_time"], seed["end_time"]) != (
            seeds[first]["start_time"],
            seeds[first]["end_time"],
        ):
            entry[2] = ancestor
    kept = [] if latest_unmerged is None else [latest_unmerged]
    for first, latest, split in by_group.values():
        for ancestor in (first, latest, split):
            if ancestor is not None and ancestor not in kept:
                kept.append(ancestor)
    return tuple(kept)


def validate_piece_seed_precedence(*, scope, groups, seed_results, execution_completed_op_ids):
    seeds = {row["op_id"]: row for row in seed_results}
    if len(seeds) != len(seed_results):
        fail("piece_protected_seed_missing", "要保持原安排的工序出现了重复记录，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    if not execution_completed_op_ids <= set(seeds):
        fail("piece_protected_seed_missing", "已完工的单件工序缺少准确的实际起止时间，这次排产没有开始。请到现场记录补齐后重试。")
    max_seed_seq_by_group = {}
    seed_count_by_group = {}
    group_seed_ops = {}
    for work in scope.operations:
        if work.op_id not in seeds:
            continue
        group = groups.get(work.op_id)
        if group is None:
            continue
        seed_count_by_group[group] = seed_count_by_group.get(group, 0) + 1
        group_seed_ops.setdefault(group, []).append(work.op_id)
        if work.sequence > max_seed_seq_by_group.get(group, -1):
            max_seed_seq_by_group[group] = work.sequence
    active_groups = {
        op_id: (group if op_id in seeds and seed_count_by_group.get(group, 0) >= 2 else None)
        for op_id, group in groups.items()
    }

    def expire_groups(candidates, min_future_seq):
        for op_id in candidates:
            group = active_groups.get(op_id)
            if group is not None and max_seed_seq_by_group.get(group, -1) < min_future_seq:
                for member in group_seed_ops[group]:
                    active_groups[member] = None

    seeded_ancestors_by_op = {}
    for work in sorted(scope.operations, key=lambda item: (item.batch_id, item.sequence, item.op_id)):
        ancestors = [
            ancestor
            for predecessor in work.predecessor_op_ids
            for ancestor in seeded_ancestors_by_op.get(predecessor, ())
        ]
        if work.op_id in seeds:
            expire_groups(ancestors, work.sequence)
            seeded_ancestors = _reduce_seeded_ancestors(ancestors, seeds, active_groups) if ancestors else ()
            for ancestor in seeded_ancestors:
                _validate_seed_pair(ancestor, work.op_id, seeds[ancestor], seeds[work.op_id], groups)
            forwarded = (*seeded_ancestors, work.op_id)
            expire_groups(forwarded, work.sequence + 1)
            seeded_ancestors_by_op[work.op_id] = _reduce_seeded_ancestors(forwarded, seeds, active_groups)
        else:
            expire_groups(ancestors, work.sequence + 1)
            seeded_ancestors_by_op[work.op_id] = (
                _reduce_seeded_ancestors(ancestors, seeds, active_groups) if ancestors else ()
            )


def _validate_seed_pair(left_id, right_id, previous, current, groups):
    problem = protected_interval_problem(
        previous, current, previous_group=groups[left_id], current_group=groups[right_id]
    )
    if problem == "merged_group_split":
        fail("piece_merged_group_split", "同一个外协合并分组里，保持原安排的工序时段不一致，这次排产没有开始。请到现场记录核对后重试。")
    if problem == "precedence_violation":
        fail("piece_protected_precedence_violation", "保持原安排的工序和它的前道工序时间冲突，这次排产没有开始。请到现场记录核对后重试。")
