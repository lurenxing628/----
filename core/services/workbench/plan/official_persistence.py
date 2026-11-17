"""Persist an already validated complete plan in the caller's write transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Mapping, NoReturn, Optional, Tuple

from core.infrastructure.operation_logging import OperationLogger
from core.services.workbench.facts.candidate_facts import RESOURCE_TABLES, TABLE_KEYS
from core.services.workbench.facts.candidate_values import corrupt, is_stored_text
from core.services.workbench.facts.gantt_graph import build_gantt_graph
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.production_capture import ArchivedTables
from core.shared.local_datetime import datetime_to_us, us_to_iso
from core.shared.refs import new_ref
from core.shared.strict_json import canonical_json
from core.shared.strict_parse import wire_int
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from data.repositories.schedule_repo import ScheduleRepository


@dataclass(frozen=True)
class AdoptedResource:
    """A machine, operator or supplier as an adopted task records it: its permanent ref and its name.

    Taken from the facts the adoption was validated against; an official plan source's supplier keeps the ref and
    label its plan stored (``Schedule`` columns, nullable). A task without the resource records neither. A recorded
    resource is admitted by ``adopted_resource``.
    """

    ref: Optional[str]
    label: Optional[str]


NO_RESOURCE = AdoptedResource(None, None)


def adopted_label(value: Any, on_corrupt: Callable[[], NoReturn]) -> str:
    """A name an adopted task records (its resource's or its operation type's), kept as its archive stored it. One
    readers would not show (``candidate_values.is_stored_text``, the readers' ``text`` rule) is that archive's
    corruption: ``on_corrupt`` rejects it and the official plan is not written."""
    if not is_stored_text(value):
        on_corrupt()
    return value


def adopted_resource(ref: str, name: Any, on_corrupt: Callable[[], NoReturn]) -> AdoptedResource:
    """The resource an adopted task records under the name its archive stored (``adopted_label``)."""
    return AdoptedResource(ref, adopted_label(name, on_corrupt))


def generation_resource(facts, kind: str, key: Optional[str]) -> AdoptedResource:
    """One resource of a run's generation facts, read through their archive relations; a task without one
    (``key`` empty) has none."""
    if not key:
        return NO_RESOURCE
    return adopted_resource(facts.entity_ref(kind, key), facts.related(RESOURCE_TABLES[kind], key)["name"], corrupt)


def archived_resources(tables: ArchivedTables) -> Dict[Tuple[str, str], Tuple[str, Any]]:
    """Every machine, operator and supplier of an admitted archive's tables by ``(kind, key)``: its ref and stored
    name, admitted (``adopted_resource``) only for a resource a task records."""
    refs = {
        (row["kind"], row["entity_key"]): row["ref"]
        for row in tables["WorkbenchEntityRefs"]
        if row["active"] == 1
    }
    result = {}
    for kind, name in RESOURCE_TABLES.items():
        column = TABLE_KEYS[name]
        for row in tables[name]:
            result[(kind, row[column])] = (refs[(kind, row[column])], row["name"])
    return result


@dataclass(frozen=True)
class OfficialPlanWrite:
    """What one persisted official plan wrote: the plan's identity, its task count, and the adoption and schedule
    times its ``ScheduleHistory`` head records."""

    official_plan: Dict[str, Any]
    row_count: int
    adopted_at: str
    schedule_time: str


def build_task_snapshot(
    *,
    operation: Mapping[str, Any],
    batch: Mapping[str, Any],
    execution: Mapping[str, Any],
    quantity_basis: str,
    op_type_ref: Optional[str],
    op_type_label: Optional[str],
    machine: AdoptedResource,
    operator: AdoptedResource,
    supplier: AdoptedResource,
) -> Dict[str, Any]:
    """One adopted task's recorded facts; ``op_type_label`` is already admitted (``adopted_label``) by the caller,
    which knows its archive, or None where that archive records no type name."""
    remaining_raw = execution["remaining_quantity"]
    remaining_quantity = int(remaining_raw) if remaining_raw is not None else None
    return {
        "op_type_ref": op_type_ref,
        "op_type_label": op_type_label,
        "quantity": int(execution["target_quantity"]),
        "remaining_quantity": remaining_quantity,
        "batch_quantity": int(batch["quantity"]),
        "quantity_basis": quantity_basis,
        "quantity_reason": None,
        "machine_ref": machine.ref,
        "machine_label": machine.label,
        "operator_ref": operator.ref,
        "operator_label": operator.label,
        "supplier_id": operation["supplier_id"],
        "supplier_ref": supplier.ref,
        "supplier_label": supplier.label,
    }


def persist_official_plan_in_tx(
    conn,
    *,
    prepared,
    payload,
    baseline,
    provenance: Mapping[str, Any],
    task_snapshots: Mapping[int, Mapping[str, Any]],
    audit: Mapping[str, Any],
    application_operator: str,
    adopted_at: datetime,
    run_window=None,
) -> OfficialPlanWrite:
    """``adopted_at`` is the adoption request's one reading of its clock, recorded to the second.

    ``run_window`` holds the dates of the run that left stage work pending.
    None means ``prepared`` is that run's own input (candidate adoption). A trial
    passes its source's recorded dates.
    """
    if not conn.in_transaction:
        raise RuntimeError("Official plan persistence requires the caller's write transaction")
    log_detail = dict(audit)
    action = log_detail.pop("action")
    history = ScheduleHistoryRepository(conn)
    version = history.allocate_next_version()
    plan_ref = new_ref()
    adopted_text = adopted_at.isoformat(timespec="seconds")

    # 锁定只标已开工、做完的工序（它们由报工记录保护）。因不重排时段保留的不锁：时段只管这一次排产
    # （另记在 material_policy 里，试调据此判断），否则一旦采用就钉死，以后填"不设"也放不开。
    locked_ids = prepared.execution_guard.execution_completed_op_ids
    ops_by_id = {op.id: op for op in prepared.operations}
    dispositions_by_op_id = {item["op_id"]: item for item in prepared.dispositions}
    relations = {
        item["operation_ref"]: item["predecessor_refs"]
        for item in prepared.dispositions
    }

    rows = []
    graph_tasks = []
    task_intervals = {}
    for row in payload.schedule_rows:
        op = ops_by_id[row.op_id]
        batch = prepared.batches[op.batch_id]
        disposition = dispositions_by_op_id[row.op_id]
        operation_ref = disposition["operation_ref"]
        snapshot = task_snapshots[row.op_id]
        task_ref = new_ref()
        rows.append(
            {
                "version": version,
                "task_ref": task_ref,
                "op_id": row.op_id,
                "operation_ref": operation_ref,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "batch_id": op.batch_id,
                "batch_priority": batch.priority,
                "piece_id": op.piece_id,
                "seq": op.seq,
                "op_type_name": op.op_type_name,
                "op_type_ref": snapshot["op_type_ref"],
                "op_type_label": snapshot["op_type_label"],
                "source": row.source,
                "setup_hours": float(op.setup_hours) if op.setup_hours is not None else None,
                "unit_hours": float(op.unit_hours) if op.unit_hours is not None else None,
                "quantity": snapshot["quantity"],
                "remaining_quantity": snapshot["remaining_quantity"],
                "batch_quantity": snapshot["batch_quantity"],
                "quantity_basis": snapshot["quantity_basis"],
                "quantity_reason": snapshot["quantity_reason"],
                "machine_id": row.machine_id,
                "machine_ref": snapshot["machine_ref"],
                "machine_label": snapshot["machine_label"],
                "operator_id": row.operator_id,
                "operator_ref": snapshot["operator_ref"],
                "operator_label": snapshot["operator_label"],
                "supplier_id": snapshot["supplier_id"],
                "supplier_ref": snapshot["supplier_ref"],
                "supplier_label": snapshot["supplier_label"],
                "lock_status": "locked" if row.op_id in locked_ids else "unlocked",
            }
        )
        graph_tasks.append(
            {
                "task_ref": task_ref,
                "operation_ref": operation_ref,
                "batch_id": op.batch_id,
                "piece_id": op.piece_id,
                "sequence": wire_int(op.seq),
                "process_label": op.op_type_name,
                "start": row.start_time.isoformat(),
                "end": row.end_time.isoformat(),
                "machine_ref": row.machine_id,
                "operator_ref": row.operator_id,
            }
        )
        task_intervals[task_ref] = (row.start_time, row.end_time)

    gantt_graph = build_gantt_graph(
        graph_tasks,
        relations,
        scope="full_plan",
        task_intervals=task_intervals,
    )
    plan_start = min(row.start_time for row in payload.schedule_rows)
    plan_end = max(row.end_time for row in payload.schedule_rows)
    plan_start_time = us_to_iso(datetime_to_us(plan_start))
    plan_end_time = us_to_iso(datetime_to_us(plan_end))
    end_includes_point = int(
        any(row.end_time == plan_end and row.start_time == row.end_time for row in payload.schedule_rows)
    )
    material_policy = _material_policy(prepared.settings, run_window)
    deferred_operation_ids = sorted(material_deferred_ids(prepared.dispositions, prepared.settings))

    # Must insert ScheduleHistory head FIRST so Schedule(version) FK is satisfied.
    schedule_time = history.create(
        {
            "version": version,
            "plan_ref": plan_ref,
            "adopted_at": adopted_text,
            "strategy": "manual",
            "batch_count": len(prepared.batches),
            "op_count": len(rows),
            "result_status": "success",
            "created_by": application_operator,
            "request_key": log_detail["request_key"],
            "declared_operator": log_detail["declared_operator"],
            "application_operator": application_operator,
            "reason": log_detail["reason"],
            "source_kind": provenance["source_kind"],
            "source_ref": provenance["source_ref"],
            "source_label": provenance["source_label"],
            "run_ref": provenance["run_ref"],
            "draft_ref": provenance["draft_ref"],
            "accepted_at": provenance["accepted_at"],
            "finished_at": provenance["finished_at"],
            "algorithm_json": provenance["algorithm_json"],
            "baseline_version": provenance["baseline_version"],
            "baseline_ref": provenance["baseline_ref"],
            "baseline_kind": provenance["baseline_kind"],
            "baseline_captured_at": provenance["baseline_captured_at"],
            "baseline_captured_task_count": provenance["baseline_captured_task_count"],
            "material_policy_json": canonical_json(material_policy),
            "deferred_operation_ids_json": canonical_json(deferred_operation_ids),
            "operation_effort_json": (
                canonical_json(provenance["operation_effort"])
                if provenance["operation_effort"] is not None
                else None
            ),
            "plan_start_time": plan_start_time,
            "plan_end_time": plan_end_time,
            "end_includes_point": end_includes_point,
            "gantt_node_count": len(gantt_graph["nodes"]),
            "gantt_graph_json": canonical_json(gantt_graph),
        }
    )
    ScheduleRepository(conn).bulk_create(rows)

    log_detail.update(
        plan_ref=plan_ref,
        baseline_ref=baseline["plan_ref"],
        baseline_version=baseline["version"],
        version=version,
        validation="valid",
        row_count=len(rows),
        application_operator=application_operator,
        adopted_at=adopted_text,
        is_simulation=False,
        material_policy=material_policy,
        deferred_operation_ids=deferred_operation_ids,
    )
    OperationLogger(conn).info(
        "scheduler",
        action,
        target_type="schedule",
        target_id=plan_ref,
        operator=application_operator,
        detail=log_detail,
        raise_on_fail=True,
    )

    identity = {
        "plan_ref": plan_ref,
        "version": version,
        "kind": "official",
        "is_current_official": True,
        "display_name": "正式计划 v" + str(version),
        "baseline_ref": baseline["plan_ref"],
        "completeness": "complete",
        "capabilities": {"view": True, "edit_draft": False, "adopt": False, "report_actual": True},
        "blocked_reasons": [],
    }
    return OfficialPlanWrite(identity, len(rows), adopted_text, schedule_time)


def _material_policy(settings, run_window):
    # 排产起止日和不重排时段一起记下，从这份正式计划发起的试调按同一时段判断哪些原安排不能改。
    if run_window is None:
        # hold_window is optional in a run input; the run dates never are.
        run_window = {
            "start_date": settings["start_date"],
            "end_date": settings["end_date"],
            **({"hold_window": settings["hold_window"]} if "hold_window" in settings else {}),
        }
    return {
        "ready_check": settings["ready_check"],
        "material_strategy": settings["material_strategy"],
        **run_window,
    }
