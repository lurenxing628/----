"""Real-schema fixtures and self-sufficient ScheduleHistory/Schedule helpers; no app startup."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.services.workbench.facts.gantt_graph import build_gantt_graph, frozen_process_relations
from core.shared.local_datetime import datetime_to_us, row_interval, us_to_iso
from core.shared.refs import new_ref
from core.shared.strict_json import canonical_json

START = "2026-09-09T08:00:00"
END = "2026-09-09T09:00:00"
_UNSET = object()


def normalize_schedule_time(raw: str) -> Tuple[str, int]:
    dt = datetime.fromisoformat(raw)
    return dt.isoformat(timespec="microseconds" if dt.microsecond else "seconds"), datetime_to_us(dt)


def seed_operation(conn):
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('CAT-P', 'Catalog part')")
    conn.execute("INSERT INTO Batches(batch_id, part_no, quantity) VALUES ('CAT-B', 'CAT-P', 1)")
    return conn.execute(
        "INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) VALUES ('CAT-OP', 'CAT-B', 1, 'Catalog op')"
    ).lastrowid


def _empty_graph_json() -> str:
    return canonical_json(build_gantt_graph([], {}, scope="full_plan", task_intervals={}))


def ensure_history_head(
    conn,
    version: int,
    *,
    plan_ref: Optional[str] = None,
    status: str = "success",
    strategy: str = "catalog",
    schedule_time: str = START,
    adopted_at: Optional[str] = None,
    created_by: str = "pytest",
    request_key: Optional[str] = None,
    declared_operator: Optional[str] = None,
    application_operator: Optional[str] = None,
    reason: Optional[str] = None,
    source_kind: str = "candidate_adoption",
    source_ref: Optional[str] = None,
    source_label: Optional[str] = None,
    run_ref: Any = _UNSET,
    draft_ref: Any = _UNSET,
    accepted_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    algorithm_json: Optional[str] = None,
    baseline_version: Optional[int] = None,
    baseline_ref: Optional[str] = None,
    baseline_kind: Optional[str] = None,
    baseline_captured_at: Optional[str] = None,
    baseline_captured_task_count: int = 0,
    material_policy: Optional[Dict[str, Any]] = None,
    deferred_operation_ids: Optional[Iterable[int]] = None,
    operation_effort: Optional[Dict[str, Any]] = None,
) -> str:
    existing = conn.execute("SELECT plan_ref FROM ScheduleHistory WHERE version = ?", (int(version),)).fetchone()
    if existing is not None:
        return str(existing[0])
    ref = plan_ref if plan_ref is not None else new_ref()
    adopted_iso, _ = normalize_schedule_time(adopted_at if adopted_at is not None else schedule_time)
    src_ref = source_ref if source_ref is not None else new_ref()
    resolved_run_ref = (new_ref() if source_kind == "candidate_adoption" else None) if run_ref is _UNSET else run_ref
    resolved_draft_ref = (new_ref() if source_kind == "trial_adoption" else None) if draft_ref is _UNSET else draft_ref
    b_kind = baseline_kind if baseline_kind is not None else (
        "trial_creation_official" if source_kind == "trial_adoption" else "admission_official"
    )
    b_captured_at = baseline_captured_at if baseline_captured_at is not None else (accepted_at or adopted_iso)
    policy_json = canonical_json(
        material_policy
        if material_policy is not None
        else {
            "ready_check": True,
            "material_strategy": "strict",
            "start_date": adopted_iso[:10],
            "end_date": adopted_iso[:10],
        }
    )
    deferred_json = canonical_json(list(deferred_operation_ids) if deferred_operation_ids is not None else [])
    effort_json = canonical_json(operation_effort) if operation_effort is not None else None
    conn.execute(
        """INSERT INTO ScheduleHistory (
            version, plan_ref, schedule_time, adopted_at, strategy, batch_count, op_count,
            result_status, created_by, request_key, declared_operator, application_operator, reason,
            source_kind, source_ref, source_label, run_ref, draft_ref, accepted_at, finished_at,
            algorithm_json, baseline_version, baseline_ref, baseline_kind, baseline_captured_at,
            baseline_captured_task_count, material_policy_json, deferred_operation_ids_json,
            operation_effort_json, plan_start_time, plan_end_time, end_includes_point,
            gantt_node_count, gantt_graph_json
        ) VALUES (
            ?, ?, ?, ?, ?, 0, 0,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, 0,
            0, ?
        )""",
        (
            int(version),
            ref,
            schedule_time,
            adopted_iso,
            strategy,
            status,
            created_by,
            request_key,
            declared_operator,
            application_operator,
            reason,
            source_kind,
            src_ref,
            source_label,
            resolved_run_ref,
            resolved_draft_ref,
            accepted_at,
            finished_at,
            algorithm_json,
            baseline_version,
            baseline_ref,
            b_kind,
            b_captured_at,
            int(baseline_captured_task_count),
            policy_json,
            deferred_json,
            effort_json,
            adopted_iso,
            adopted_iso,
            _empty_graph_json(),
        ),
    )
    return ref


def _build_plan_gantt_graph(conn, s_rows) -> Dict[str, Any]:
    if not s_rows:
        return build_gantt_graph([], {}, scope="full_plan", task_intervals={})
    batch_ids = sorted({r["batch_id"] for r in s_rows})
    batch_json = json.dumps(batch_ids)
    batches = {
        r[0]: {"quantity": r[1]}
        for r in conn.execute(
            "SELECT batch_id, quantity FROM Batches WHERE batch_id IN (SELECT value FROM json_each(?))",
            (batch_json,),
        )
    }
    op_cursor = conn.execute(
        """SELECT bo.*, r.ref AS operation_ref
           FROM BatchOperations bo
           JOIN WorkbenchPlanSourceRefs r
             ON r.kind = 'operation' AND r.active = 1 AND r.source_key = CAST(bo.id AS TEXT)
           WHERE bo.batch_id IN (SELECT value FROM json_each(?))""",
        (batch_json,),
    )
    col_names = [d[0] for d in op_cursor.description]
    operations: Dict[int, Dict[str, Any]] = {}
    refs: Dict[int, str] = {}
    for raw_row in op_cursor:
        op_dict = dict(zip(col_names, raw_row))
        op_id = int(op_dict["id"])
        refs[op_id] = op_dict.pop("operation_ref")
        operations[op_id] = op_dict
    relations = frozen_process_relations(operations, batches, refs)
    tasks = []
    task_intervals = {}
    for r in s_rows:
        t_ref = r["task_ref"]
        tasks.append(
            {
                "task_ref": t_ref,
                "operation_ref": r["operation_ref"],
                "batch_id": r["batch_id"],
                "piece_id": r["piece_id"],
                "sequence": r["seq"],
                "process_label": r["op_type_name"],
                "start": r["start_time"],
                "end": r["end_time"],
                "machine_ref": r["machine_ref"],
                "operator_ref": r["operator_ref"],
            }
        )
        task_intervals[t_ref] = row_interval(r)
    return build_gantt_graph(tasks, relations, scope="full_plan", task_intervals=task_intervals)


def sync_history_from_schedule(conn, version: int) -> None:
    cursor = conn.execute(
        """SELECT task_ref, operation_ref, start_time, end_time, start_us, end_us, is_point_event,
                  batch_id, piece_id, seq, op_type_name, machine_ref, operator_ref
           FROM Schedule
           WHERE version = ?
           ORDER BY start_us ASC, id ASC""",
        (int(version),),
    )
    cols = [d[0] for d in cursor.description]
    s_rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    if not s_rows:
        head = conn.execute("SELECT adopted_at FROM ScheduleHistory WHERE version = ?", (int(version),)).fetchone()
        if head is None:
            return
        adopted_iso = head[0]
        conn.execute(
            """UPDATE ScheduleHistory
               SET batch_count = 0, op_count = 0, plan_start_time = ?, plan_end_time = ?,
                   end_includes_point = 0, gantt_node_count = 0, gantt_graph_json = ?
               WHERE version = ?""",
            (adopted_iso, adopted_iso, _empty_graph_json(), int(version)),
        )
        return
    min_start_us = min(int(r["start_us"]) for r in s_rows)
    max_end_us = max(int(r["end_us"]) for r in s_rows)
    end_includes_point = 1 if any(int(r["end_us"]) == max_end_us and int(r["is_point_event"]) == 1 for r in s_rows) else 0
    batch_count = len({r["batch_id"] for r in s_rows})
    graph = _build_plan_gantt_graph(conn, s_rows)
    conn.execute(
        """UPDATE ScheduleHistory
           SET batch_count = ?, op_count = ?, plan_start_time = ?, plan_end_time = ?,
               end_includes_point = ?, gantt_node_count = ?, gantt_graph_json = ?
           WHERE version = ?""",
        (
            batch_count,
            len(s_rows),
            us_to_iso(min_start_us),
            us_to_iso(max_end_us),
            end_includes_point,
            len(graph["nodes"]),
            canonical_json(graph),
            int(version),
        ),
    )


def _resource_maps(conn, kind: str, table: str, key_col: str, keys: Iterable[str]) -> Tuple[Dict[str, str], Dict[str, Optional[str]]]:
    unique_keys = sorted({k for k in keys if k not in (None, "")})
    if not unique_keys:
        return {}, {}
    keys_json = json.dumps(unique_keys)
    names = {
        r[0]: r[1]
        for r in conn.execute(
            f"SELECT {key_col}, name FROM {table} WHERE {key_col} IN (SELECT value FROM json_each(?))",
            (keys_json,),
        )
    }
    refs = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT entity_key, ref FROM WorkbenchEntityRefs "
            "WHERE kind = ? AND active = 1 AND entity_key IN (SELECT value FROM json_each(?))",
            (kind, keys_json),
        )
    }
    return refs, names


def insert_schedule_rows(
    conn,
    version: int,
    items: Iterable[Dict[str, Any]],
    *,
    sync_history: bool = True,
    quantity_basis: str = "run_admission",
) -> List[str]:
    item_list = list(items)
    if not item_list:
        return []
    first_start = item_list[0]["start_time"]
    ensure_history_head(conn, int(version), schedule_time=first_start)
    op_ids = sorted({int(item["op_id"]) for item in item_list})
    op_cursor = conn.execute(
        """SELECT bo.id AS op_id, bo.batch_id, bo.piece_id, bo.seq, bo.op_type_id, bo.op_type_name,
                  bo.source, bo.setup_hours, bo.unit_hours, bo.machine_id, bo.operator_id, bo.supplier_id,
                  b.priority AS batch_priority, b.quantity AS batch_quantity,
                  r.ref AS operation_ref
           FROM BatchOperations bo
           JOIN Batches b ON b.batch_id = bo.batch_id
           JOIN WorkbenchPlanSourceRefs r
             ON r.kind = 'operation' AND r.active = 1 AND r.source_key = CAST(bo.id AS TEXT)
           WHERE bo.id IN (SELECT value FROM json_each(?))""",
        (json.dumps(op_ids),),
    )
    op_cols = [d[0] for d in op_cursor.description]
    ops_by_id = {int(row[0]): dict(zip(op_cols, row)) for row in op_cursor.fetchall()}

    op_type_ids = [op["op_type_id"] for op in ops_by_id.values() if op["op_type_id"] not in (None, "")]
    machine_ids: List[str] = []
    operator_ids: List[str] = []
    supplier_ids: List[str] = []
    for item in item_list:
        op = ops_by_id[int(item["op_id"])]
        src = op["source"]
        m_id = item["machine_id"] if "machine_id" in item else (op["machine_id"] if src == "internal" else None)
        o_id = item["operator_id"] if "operator_id" in item else (op["operator_id"] if src == "internal" else None)
        s_id = item["supplier_id"] if "supplier_id" in item else (op["supplier_id"] if src == "external" else None)
        if m_id not in (None, ""):
            machine_ids.append(m_id)
        if o_id not in (None, ""):
            operator_ids.append(o_id)
        if s_id not in (None, ""):
            supplier_ids.append(s_id)

    ot_refs, ot_names = _resource_maps(conn, "op_type", "OpTypes", "op_type_id", op_type_ids)
    m_refs, m_names = _resource_maps(conn, "machine", "Machines", "machine_id", machine_ids)
    o_refs, o_names = _resource_maps(conn, "operator", "Operators", "operator_id", operator_ids)
    s_refs, s_names = _resource_maps(conn, "supplier", "Suppliers", "supplier_id", supplier_ids)

    params: List[Tuple[Any, ...]] = []
    task_refs: List[str] = []
    for item in item_list:
        op = ops_by_id[int(item["op_id"])]
        source = op["source"]
        start_iso, start_us = normalize_schedule_time(item["start_time"])
        end_iso, end_us = normalize_schedule_time(item["end_time"])
        is_point = 1 if start_us == end_us else 0
        t_ref = item["task_ref"] if "task_ref" in item and item["task_ref"] is not None else new_ref()
        task_refs.append(t_ref)
        ot_id = op["op_type_id"]
        ot_ref = (
            item["op_type_ref"]
            if "op_type_ref" in item
            else (ot_refs.get(ot_id) if ot_id not in (None, "") else None)
        )
        ot_label = (
            item["op_type_label"]
            if "op_type_label" in item
            else (ot_names.get(ot_id, op["op_type_name"]) if ot_id not in (None, "") else op["op_type_name"])
        )

        m_id = item["machine_id"] if "machine_id" in item else (op["machine_id"] if source == "internal" else None)
        o_id = item["operator_id"] if "operator_id" in item else (op["operator_id"] if source == "internal" else None)
        s_id = item["supplier_id"] if "supplier_id" in item else (op["supplier_id"] if source == "external" else None)

        m_ref = m_refs.get(m_id) if m_id not in (None, "") else None
        m_label = m_names.get(m_id) if m_id not in (None, "") else None
        o_ref = o_refs.get(o_id) if o_id not in (None, "") else None
        o_label = o_names.get(o_id) if o_id not in (None, "") else None
        s_ref = s_refs.get(s_id) if s_id not in (None, "") else None
        s_label = s_names.get(s_id) if s_id not in (None, "") else None

        batch_qty = op["batch_quantity"]
        default_qty = (1 if op["piece_id"] is not None else batch_qty) if batch_qty is not None else None
        qty = item["quantity"] if "quantity" in item else default_qty
        rem_qty = item["remaining_quantity"] if "remaining_quantity" in item else qty
        q_basis = item["quantity_basis"] if "quantity_basis" in item else quantity_basis
        q_reason = item["quantity_reason"] if "quantity_reason" in item else None
        lock_status = item["lock_status"] if "lock_status" in item else "unlocked"
        sched_id = item["id"] if "id" in item else None

        params.append(
            (
                sched_id,
                int(version),
                t_ref,
                int(item["op_id"]),
                op["operation_ref"],
                start_iso,
                end_iso,
                start_us,
                end_us,
                is_point,
                op["batch_id"],
                op["batch_priority"],
                op["piece_id"],
                int(op["seq"]),
                op["op_type_name"],
                ot_ref,
                ot_label,
                source,
                float(op["setup_hours"]) if op["setup_hours"] is not None else None,
                float(op["unit_hours"]) if op["unit_hours"] is not None else None,
                qty,
                rem_qty,
                batch_qty,
                q_basis,
                q_reason,
                m_id,
                m_ref,
                m_label,
                o_id,
                o_ref,
                o_label,
                s_id,
                s_ref,
                s_label,
                lock_status,
            )
        )

    conn.executemany(
        """INSERT INTO Schedule (
            id, version, task_ref, op_id, operation_ref,
            start_time, end_time, start_us, end_us, is_point_event,
            batch_id, batch_priority, piece_id, seq,
            op_type_name, op_type_ref, op_type_label,
            source, setup_hours, unit_hours,
            quantity, remaining_quantity, batch_quantity, quantity_basis, quantity_reason,
            machine_id, machine_ref, machine_label,
            operator_id, operator_ref, operator_label,
            supplier_id, supplier_ref, supplier_label,
            lock_status
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?
        )""",
        params,
    )
    if sync_history:
        sync_history_from_schedule(conn, int(version))
    return task_refs


def insert_schedule_row(
    conn,
    version: int,
    op_id: int,
    start_time: str,
    end_time: str,
    *,
    schedule_id: Optional[int] = None,
    task_ref: Optional[str] = None,
    machine_id: Any = _UNSET,
    operator_id: Any = _UNSET,
    supplier_id: Any = _UNSET,
    lock_status: str = "unlocked",
    sync_history: bool = True,
) -> str:
    item: Dict[str, Any] = {
        "op_id": op_id,
        "start_time": start_time,
        "end_time": end_time,
        "lock_status": lock_status,
    }
    if schedule_id is not None:
        item["id"] = schedule_id
    if task_ref is not None:
        item["task_ref"] = task_ref
    if machine_id is not _UNSET:
        item["machine_id"] = machine_id
    if operator_id is not _UNSET:
        item["operator_id"] = operator_id
    if supplier_id is not _UNSET:
        item["supplier_id"] = supplier_id
    return insert_schedule_rows(conn, version, [item], sync_history=sync_history)[0]


def update_schedule_rows(
    conn,
    version: int,
    *,
    where: str = "",
    params: Iterable[Any] = (),
    start_time: Any = _UNSET,
    end_time: Any = _UNSET,
    machine_id: Any = _UNSET,
    operator_id: Any = _UNSET,
    lock_status: Any = _UNSET,
    sync_history: bool = True,
) -> None:
    clause = f"version = ? AND ({where})" if where else "version = ?"
    query_params = (int(version), *tuple(params))
    rows = conn.execute(
        f"SELECT id, start_time, end_time, machine_id, operator_id, lock_status FROM Schedule WHERE {clause}",
        query_params,
    ).fetchall()
    if not rows:
        return
    m_refs, m_names = (
        _resource_maps(conn, "machine", "Machines", "machine_id", [machine_id])
        if machine_id is not _UNSET and machine_id not in (None, "")
        else ({}, {})
    )
    o_refs, o_names = (
        _resource_maps(conn, "operator", "Operators", "operator_id", [operator_id])
        if operator_id is not _UNSET and operator_id not in (None, "")
        else ({}, {})
    )
    updates: List[Tuple[Any, ...]] = []
    for r_id, cur_start, cur_end, cur_m, cur_o, cur_lock in rows:
        s_iso, s_us = normalize_schedule_time(cur_start if start_time is _UNSET else start_time)
        e_iso, e_us = normalize_schedule_time(cur_end if end_time is _UNSET else end_time)
        is_point = 1 if s_us == e_us else 0
        if machine_id is _UNSET:
            m_val = cur_m
            keep_m = True
        else:
            m_val = machine_id
            keep_m = False
        if operator_id is _UNSET:
            o_val = cur_o
            keep_o = True
        else:
            o_val = operator_id
            keep_o = False
        lock_val = cur_lock if lock_status is _UNSET else lock_status
        updates.append((s_iso, e_iso, s_us, e_us, is_point, lock_val, r_id, keep_m, m_val, keep_o, o_val))

    for s_iso, e_iso, s_us, e_us, is_point, lock_val, r_id, keep_m, m_val, keep_o, o_val in updates:
        sets = ["start_time = ?", "end_time = ?", "start_us = ?", "end_us = ?", "is_point_event = ?", "lock_status = ?"]
        vals: List[Any] = [s_iso, e_iso, s_us, e_us, is_point, lock_val]
        if not keep_m:
            m_ref = m_refs.get(m_val) if m_val not in (None, "") else None
            m_label = m_names.get(m_val) if m_val not in (None, "") else None
            sets.extend(["machine_id = ?", "machine_ref = ?", "machine_label = ?"])
            vals.extend([m_val, m_ref, m_label])
        if not keep_o:
            o_ref = o_refs.get(o_val) if o_val not in (None, "") else None
            o_label = o_names.get(o_val) if o_val not in (None, "") else None
            sets.extend(["operator_id = ?", "operator_ref = ?", "operator_label = ?"])
            vals.extend([o_val, o_ref, o_label])
        vals.append(r_id)
        conn.execute("UPDATE Schedule SET " + ", ".join(sets) + " WHERE id = ?", vals)

    if sync_history:
        sync_history_from_schedule(conn, int(version))


def history(
    conn,
    version: int,
    status: str = "success",
    *,
    op_id: Optional[int] = None,
    time: str = START,
    baseline_version: Optional[int] = None,
    baseline_ref: Optional[str] = None,
) -> str:
    plan_ref = ensure_history_head(
        conn,
        version,
        status=status,
        strategy="catalog",
        schedule_time=time,
        baseline_version=baseline_version,
        baseline_ref=baseline_ref,
    )
    if op_id is not None:
        insert_schedule_row(conn, version, op_id, START, END)
    return plan_ref
