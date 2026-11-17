from __future__ import annotations

from collections import defaultdict
from typing import List, Set

from core.algorithm_contracts.resource_pool import DISABLED_RESOURCE_POOL, ResourcePool
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import INTERNAL
from core.models.enums import SKILL_LEVEL_RANKS, MachineStatus, OperatorStatus, YesNo
from core.models.machine import Machine
from core.services.personnel.operator_qualification import (
    OperatorQualificationService,
    require_explicit_auto_work_types,
    require_machine_authorization,
    require_work_type_qualification,
)

RESOURCE_FACT_TABLES = (
    "Machines",
    "MachineOpTypes",
    "Operators",
    "OperatorMachine",
    "WorkbenchOperatorProfiles",
    "OpTypes",
    "OperatorSkill",
)


class CapturedResourceFacts:
    """Resources derived from this operation's captured rows, with demand-scoped qualifications."""

    def __init__(self, tables):
        # 这些编号是库里的主键或 NOT NULL 外键，准入边界已拒绝空值与空白，读取与排产保留存量原值。
        capabilities = defaultdict(list)
        for row in tables["MachineOpTypes"]:
            capabilities[row["machine_id"]].append(row["op_type_id"])
        self.machines = [
            Machine.from_row(dict(row, op_type_ids=tuple(capabilities[row["machine_id"]])))
            for row in sorted(tables["Machines"], key=lambda row: row["machine_id"])
            if row["status"] == MachineStatus.ACTIVE.value
        ]
        self.operators = {row["operator_id"]: row for row in tables["Operators"]}
        self.links = list(tables["OperatorMachine"])
        self._authorized_pairs = {(row["operator_id"], row["machine_id"]) for row in self.links}
        self._profiles = defaultdict(list)
        self._skills = defaultdict(list)
        for row in tables["WorkbenchOperatorProfiles"]:
            self._profiles[row["operator_id"]].append(row)
        op_types = {row["op_type_id"]: row for row in tables["OpTypes"]}
        for row in tables["OperatorSkill"]:
            self._skills[row["operator_id"]].append(
                dict(row, category=op_types.get(row["op_type_id"], {}).get("category"))
            )
        self._qualifications = {}

    def qualifications_for(self, operator_ids):
        ids = set(operator_ids)
        missing = ids - self._qualifications.keys()
        if missing:
            ordered_missing = sorted(missing)
            profiles, skills = [], []
            for oid in ordered_missing:
                if oid in self.operators:
                    stored = self._profiles.get(oid, ())
                    if stored:
                        profiles.extend({"operator_id": oid, "profile_operator_id": row["operator_id"],
                                         "skills_declared": row["skills_declared"]} for row in stored)
                    else:
                        profiles.append({"operator_id": oid, "profile_operator_id": None, "skills_declared": None})
                skills.extend(self._skills.get(oid, ()))
            self._qualifications.update(OperatorQualificationService.project_facts(ordered_missing, profiles, skills))
        return {oid: self._qualifications[oid] for oid in sorted(ids)}

    def validate_fixed(self, operations):
        """Fixed internal operators must be authorized for their machine and qualified for their work type."""
        selected = [op for op in operations if op.source == INTERNAL and op.operator_id]
        if not selected:
            return
        qualifications = self.qualifications_for(op.operator_id for op in selected)
        checked_pairs, checked_work_types = set(), set()
        for op in selected:
            pair = op.operator_id, op.machine_id
            if pair not in checked_pairs:
                require_machine_authorization(self._authorized_pairs, *pair)
                checked_pairs.add(pair)
            work_type = op.operator_id, op.op_type_id
            if work_type not in checked_work_types:
                require_work_type_qualification(qualifications, *work_type)
                checked_work_types.add(work_type)


def _op_type_ids_for_ops(algo_ops: List[OpForScheduleAlgo]) -> Set[str]:
    # 排产输入构建已核验来源与工种编号非空，保留存量原值。
    return {o.op_type_id for o in algo_ops if o.source == INTERNAL}


def _machines_by_op_type(machines, *, op_type_ids):
    result = {}
    for machine in machines:
        for op_type_id in machine.op_type_ids:
            if op_type_ids and op_type_id not in op_type_ids:
                continue
            result.setdefault(op_type_id, []).append(machine.machine_id)
    for op_type_id in sorted(op_type_ids):
        result.setdefault(op_type_id, [])
    return {op_type_id: tuple(machine_ids) for op_type_id, machine_ids in result.items()}


def _build_operator_machine_maps(rows):
    operators_by_machine, machines_by_operator, pair_rank = {}, {}, {}
    for row in rows:
        oid, mid = row["operator_id"], row["machine_id"]
        # is_primary、skill_level 由存储 CHECK 限定为规范值，直接取业务序。
        primary = row["is_primary"] == YesNo.YES.value
        rank = (0 if primary else 1) * 10 + SKILL_LEVEL_RANKS[row["skill_level"]]
        operators_by_machine.setdefault(mid, []).append((rank, oid))
        machines_by_operator.setdefault(oid, []).append(mid)
        pair_rank[oid, mid] = rank
    ordered = {mid: tuple(oid for _, oid in sorted(items)) for mid, items in operators_by_machine.items()}
    return ordered, {oid: tuple(mids) for oid, mids in machines_by_operator.items()}, pair_rank


def _consumed_resource_links(resource_facts, algo_ops: List[OpForScheduleAlgo], machines_by_op_type, active_machines):
    """A fixed pair consumes only itself; free fields consume their real candidate set."""
    open_types, fixed_machines, fixed_pairs = set(), set(), set()
    operators_by_type = defaultdict(set)
    for op in algo_ops:
        if op.source != INTERNAL:
            continue
        mid, oid = op.machine_id, op.operator_id
        op_type = op.op_type_id
        if mid and oid:
            fixed_pairs.add((oid, mid))
        elif mid:
            fixed_machines.add(mid)
        elif oid:
            operators_by_type[op_type].add(oid)
        else:
            open_types.add(op_type)
    open_machines = {mid for op_type in open_types for mid in machines_by_op_type.get(op_type, ())}
    operators_by_machine = defaultdict(set)
    for op_type, operator_ids in operators_by_type.items():
        for mid in machines_by_op_type.get(op_type, ()):
            operators_by_machine[mid].update(operator_ids)
    active_ops = {oid for oid, row in resource_facts.operators.items()
                  if row["status"] == OperatorStatus.ACTIVE.value}
    return [row for row in resource_facts.links
            if row["machine_id"] in active_machines and row["operator_id"] in active_ops
            and (row["machine_id"] in open_machines or row["machine_id"] in fixed_machines
                 or (row["operator_id"], row["machine_id"]) in fixed_pairs
                 or row["operator_id"] in operators_by_machine.get(row["machine_id"], ()))]


def _machine_ids_for_downtime_load(algo_ops):
    return sorted({op.machine_id for op in algo_ops if op.source == INTERNAL and op.machine_id is not None})


def load_machine_downtimes(*, algo_ops, start_dt, downtimes):
    """Select relevant intervals from the capture's already checked, grouped downtime."""
    return {mid: [(start, end) for start, end in downtimes.get(mid, ()) if end > start_dt]
            for mid in _machine_ids_for_downtime_load(algo_ops)}


def build_resource_pool(*, cfg, algo_ops: List[OpForScheduleAlgo], resource_facts) -> ResourcePool:
    """Build automatic assignment inputs from this operation's captured resources; without automatic
    assignment the run's pool is ``DISABLED_RESOURCE_POOL``."""
    if not cfg.auto_assign_enabled:
        return DISABLED_RESOURCE_POOL
    op_type_ids = _op_type_ids_for_ops(algo_ops)
    machines_by_op_type = _machines_by_op_type(resource_facts.machines, op_type_ids=op_type_ids)
    relevant_machines = {mid for mids in machines_by_op_type.values() for mid in mids}
    relevant_machines.update(op.machine_id for op in algo_ops
                             if op.source == INTERNAL and op.machine_id is not None)
    machines = [machine for machine in resource_facts.machines if machine.machine_id in relevant_machines]
    active_machines = {machine.machine_id for machine in machines}
    rows = _consumed_resource_links(resource_facts, algo_ops, machines_by_op_type, active_machines)
    consumed_ops = {row["operator_id"] for row in rows}
    qualifications = resource_facts.qualifications_for(consumed_ops)
    require_explicit_auto_work_types(algo_ops, rows, qualifications)
    rows = OperatorQualificationService.eligible_links(
        rows, {machine.machine_id: set(machine.op_type_ids) for machine in machines}, qualifications=qualifications)
    operators_by_machine, machines_by_operator, pair_rank = _build_operator_machine_maps(rows)
    # Skills filter operators only when a machine supports several work types.
    operator_skills = (
        {oid: None if skills is None else frozenset(skills) for oid, skills in qualifications.items()}
        if any(len(machine.op_type_ids) > 1 for machine in machines)
        else None
    )
    return ResourcePool(
        enabled=True, machines_by_op_type=machines_by_op_type, operators_by_machine=operators_by_machine,
        machines_by_operator=machines_by_operator, pair_rank=pair_rank, operator_skills=operator_skills,
    )


def extend_downtime_map_for_resource_pool(*, resource_pool: ResourcePool, downtime_map, start_dt, downtimes):
    """Include the pool's automatic assignment equipment (a disabled pool has none) using the same captured
    downtime groups."""
    for mid in resource_pool.operators_by_machine:
        if mid not in downtime_map:
            downtime_map[mid] = [(start, end) for start, end in downtimes.get(mid, ()) if end > start_dt]
    return downtime_map
