from __future__ import annotations

from collections import defaultdict
from typing import Any, List

from core.models import Machine
from core.models.enums import MachineStatus, OperatorStatus, SourceType, YesNo
from core.models.resource_capabilities import machine_types
from core.services.common.enum_normalizers import skill_rank as _skill_rank_common
from core.services.personnel.operator_qualification import (
    OperatorQualificationError,
    OperatorQualificationService,
    require_machine_authorization,
)
from core.shared.boolean_normalize import to_yes_no


class CapturedResourceFacts:
    """Resources derived from this operation's captured rows, with demand-scoped qualifications."""

    def __init__(self, tables, downtimes):
        capabilities = defaultdict(list)
        for row in tables.get("MachineOpTypes", ()):
            capabilities[row["machine_id"]].append(row["op_type_id"])
        self.machines = [Machine.from_row(dict(row, op_type_ids=tuple(capabilities[row["machine_id"]])))
                         for row in sorted(tables["Machines"], key=lambda row: row["machine_id"])
                         if row["status"] == MachineStatus.ACTIVE.value]
        self.operators = {row["operator_id"]: row for row in tables["Operators"]}
        self.links = tables["OperatorMachine"]
        self._authorized_pairs = {(row["operator_id"], row["machine_id"]) for row in self.links}
        self._profiles = defaultdict(list)
        self._skills = defaultdict(list)
        for row in tables["WorkbenchOperatorProfiles"]:
            self._profiles[row["operator_id"]].append(row)
        op_types = {row["op_type_id"]: row for row in tables["OpTypes"]}
        for row in tables["OperatorSkill"]:
            self._skills[row["operator_id"]].append(
                dict(row, category=op_types.get(row["op_type_id"], {}).get("category")))
        self._qualifications = {}
        self.downtimes = downtimes

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

    def exists(self, operator_id, machine_id):
        """Use the same authorization predicate as the editing/planning qualification service."""
        return (operator_id, machine_id) in self._authorized_pairs

    def validate_fixed(self, conn, operations, logger=None):
        selected = [op for op in operations if str(getattr(op, "source", "") or "").strip().lower() == "internal"
                    and getattr(op, "operator_id", None)]
        if not selected:
            return
        qualifications = self.qualifications_for(op.operator_id for op in selected)
        service = OperatorQualificationService(conn, logger=logger)
        checked_pairs, checked_work_types = set(), set()
        for op in selected:
            pair = op.operator_id, getattr(op, "machine_id", None)
            if pair not in checked_pairs:
                require_machine_authorization(self, *pair)
                checked_pairs.add(pair)
            work_type = op.operator_id, getattr(op, "op_type_id", None)
            if work_type not in checked_work_types:
                service.require(operator_id=work_type[0], op_type_id=work_type[1],
                                machine_id=None, qualifications=qualifications)
                checked_work_types.add(work_type)


def _op_type_ids_for_ops(algo_ops: List[Any]) -> set:
    return {
        str(getattr(o, "op_type_id", "") or "").strip()
        for o in algo_ops
        if (getattr(o, "source", "") or "").strip().lower() == SourceType.INTERNAL.value
        and str(getattr(o, "op_type_id", "") or "").strip()
    }


def _machines_by_op_type(machines, *, op_type_ids):
    result = {}
    for machine in machines:
        for op_type_id in machine_types(machine) or ("",):
            if op_type_ids and op_type_id and op_type_id not in op_type_ids:
                continue
            result.setdefault(op_type_id, []).append(machine.machine_id)
    for op_type_id in sorted(op_type_ids):
        result.setdefault(op_type_id, [])
    return result


def _build_operator_machine_maps(rows, *, active_machines, active_ops):
    operators_by_machine, machines_by_operator, pair_rank = {}, {}, {}
    for row in rows:
        oid, mid = str(row["operator_id"] or "").strip(), str(row["machine_id"] or "").strip()
        if not oid or not mid or mid not in active_machines or oid not in active_ops:
            continue
        primary = to_yes_no(row.get("is_primary"), default=YesNo.NO.value) == YesNo.YES.value
        rank = (0 if primary else 1) * 10 + _skill_rank_common(row.get("skill_level"))
        operators_by_machine.setdefault(mid, []).append((rank, oid))
        machines_by_operator.setdefault(oid, []).append(mid)
        pair_rank[oid, mid] = rank
    ordered = {mid: [oid for _, oid in sorted(items)] for mid, items in operators_by_machine.items()}
    return ordered, machines_by_operator, pair_rank


def _consumed_resource_links(resource_facts, algo_ops, machines_by_op_type, active_machines):
    """A fixed pair consumes only itself; free fields consume their real candidate set."""
    open_types, fixed_machines, fixed_pairs = set(), set(), set()
    operators_by_type = defaultdict(set)
    for op in algo_ops:
        if str(getattr(op, "source", "") or "").strip().lower() != "internal":
            continue
        mid, oid = getattr(op, "machine_id", None), getattr(op, "operator_id", None)
        op_type = getattr(op, "op_type_id", None)
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
    return sorted({str(op.machine_id).strip() for op in algo_ops
                   if (op.source or "").strip().lower() == SourceType.INTERNAL.value
                   and (op.machine_id or "").strip()})


def load_machine_downtimes(*, algo_ops, start_dt, downtimes, meta=None):
    """Select relevant intervals from the capture's already checked, grouped downtime."""
    if meta is not None:
        meta["downtime_load_ok"] = True
    return {mid: [(start, end) for start, end in downtimes.get(mid, ()) if end > start_dt]
            for mid in _machine_ids_for_downtime_load(algo_ops)}


def build_resource_pool(svc, *, cfg, algo_ops, resource_facts, meta=None):
    """Build automatic assignment inputs from this operation's captured resources."""
    if meta is not None:
        meta.update(resource_pool_attempted=False, resource_pool_build_ok=None)
    if to_yes_no(cfg.auto_assign_enabled, default=YesNo.NO.value) != YesNo.YES.value:
        return None
    if meta is not None:
        meta["resource_pool_attempted"] = True
    try:
        op_type_ids = _op_type_ids_for_ops(algo_ops)
        machines_by_op_type = _machines_by_op_type(resource_facts.machines, op_type_ids=op_type_ids)
        relevant_machines = {mid for mids in machines_by_op_type.values() for mid in mids}
        relevant_machines.update(str(op.machine_id).strip() for op in algo_ops
                                 if str(getattr(op, "source", "") or "").strip().lower() == "internal"
                                 and getattr(op, "machine_id", None))
        machines = [machine for machine in resource_facts.machines if machine.machine_id in relevant_machines]
        active_machines = {machine.machine_id for machine in machines}
        rows = _consumed_resource_links(resource_facts, algo_ops, machines_by_op_type, active_machines)
        consumed_ops = {row["operator_id"] for row in rows}
        qualifications = resource_facts.qualifications_for(consumed_ops)
        service = OperatorQualificationService(svc.conn, logger=svc.logger)
        rows = service.eligible_links(rows, machines, algo_ops, qualifications=qualifications)
        operators_by_machine, machines_by_operator, pair_rank = _build_operator_machine_maps(
            rows, active_machines=active_machines, active_ops=consumed_ops)
        pool = {"machines_by_op_type": machines_by_op_type, "operators_by_machine": operators_by_machine,
                "machines_by_operator": machines_by_operator, "pair_rank": pair_rank}
        if any(len(machine_types(machine)) > 1 for machine in machines):
            pool["operator_skills"] = {oid: sorted(skills) if skills is not None else None
                                       for oid, skills in qualifications.items()}
        if meta is not None:
            meta["resource_pool_build_ok"] = True
        return pool
    except OperatorQualificationError:
        if meta is not None:
            meta["resource_pool_build_ok"] = False
        raise


def extend_downtime_map_for_resource_pool(*, cfg, resource_pool, downtime_map, start_dt, downtimes, meta=None):
    """Include automatic assignment equipment using the same captured downtime groups."""
    if (to_yes_no(cfg.auto_assign_enabled, default=YesNo.NO.value) != YesNo.YES.value or not resource_pool
            or not isinstance(resource_pool.get("operators_by_machine"), dict)):
        return downtime_map
    if meta is not None:
        meta.update(downtime_extend_attempted=True, downtime_extend_ok=True)
    for mid in resource_pool["operators_by_machine"]:
        if mid not in downtime_map:
            downtime_map[mid] = [(start, end) for start, end in downtimes.get(mid, ()) if end > start_dt]
    return downtime_map
