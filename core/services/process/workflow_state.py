"""Content-bound confirmations; reads do not create, repair or infer metadata."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.infrastructure.workbench_resource_schema import workbench_resource_contract_issues

_STAGES = ("route", "source", "hours")


def _rows(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def _schema(conn):
    issues = (workbench_metadata_contract_issues(conn) + workbench_resource_contract_issues(conn)
              + workbench_process_contract_issues(conn) + workbench_process_workflow_contract_issues(conn))
    if issues:
        raise RuntimeError("Invalid process workflow storage: " + "; ".join(issues))


def _ref(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise RuntimeError("Missing process workflow entity identity; no metadata was repaired.")
    return value


def _part(conn, part_no):
    _schema(conn)
    rows = _rows(conn, """SELECT p.*, r.ref FROM Parts p LEFT JOIN WorkbenchEntityRefs r
        ON r.kind='part' AND r.active=1 AND r.entity_key=p.part_no WHERE p.part_no=?""", (part_no,))
    if not rows:
        raise BusinessError(ErrorCode.PART_NOT_FOUND, "零件不存在。")
    part = rows[0]
    _ref(part["ref"])
    stored = _rows(conn, "SELECT * FROM WorkbenchProcessWorkflow WHERE part_ref=?", (part["ref"],))
    return part, stored[0] if stored else None


def _digest(value):
    # Bad legacy numbers are not normalized into a confirmable business fact.
    try:
        text = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _number(value, *, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def _supplier(suppliers, supplier_id, op_type_id):
    row = suppliers.get(supplier_id)
    if row is None:
        return None, False
    fact = {"ref": _ref(row["ref"]), "status": row["status"], "inactive_reason": row["inactive_reason"],
            "capable": op_type_id is not None and op_type_id in row["capabilities"]}
    return fact, fact["status"] == "active" and fact["capable"] and fact["inactive_reason"] is None


def _operations(conn, part_no=None):
    return _rows(conn, """SELECT o.*, r.ref, t.name AS type_name, t.category,
        tr.ref AS type_ref, p.default_merge_mode FROM PartOperations o
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
            AND r.entity_key=CAST(o.id AS TEXT)
        LEFT JOIN OpTypes t ON t.op_type_id=o.op_type_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='op_type' AND tr.active=1 AND tr.entity_key=t.op_type_id
        LEFT JOIN WorkbenchOpTypePolicies p ON p.op_type_id=t.op_type_id
        WHERE o.status='active'""" + (" AND o.part_no=?" if part_no is not None else "")
                 + " ORDER BY o.part_no, o.seq, o.id", (part_no,) if part_no is not None else ())


def _groups(conn, part_no, operations):
    groups = _rows(conn, """SELECT g.*, r.ref FROM ExternalGroups g
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.active=1 AND r.entity_key=g.group_id
        WHERE g.group_id IN (SELECT ext_group_id FROM PartOperations WHERE status='active'"""
                   + (" AND part_no=?" if part_no is not None else "") + ")", (part_no,) if part_no is not None else ())
    members = {}
    for op in operations:
        members.setdefault((op["part_no"], op["ext_group_id"]), []).append([op["ref"], op["seq"], op["source"]])
    result = {}
    for group in groups:
        _ref(group["ref"])
        group["members"] = members.get((group["part_no"], group["group_id"]), [])
        fact, valid = _group_facts(group, group["part_no"])
        group["source_signature"], group["valid"] = _digest(fact), valid
        result[group["group_id"]] = group
    return result


def _group_facts(group, part_no):
    if group is None:
        return None, True
    valid_range = (type(group["start_seq"]) is int and type(group["end_seq"]) is int
                   and 0 < group["start_seq"] <= group["end_seq"])
    valid = (group["part_no"] == part_no and group["merge_mode"] in ("separate", "merged") and valid_range
             and all(source == "external" and type(seq) is int and group["start_seq"] <= seq <= group["end_seq"]
                     for _, seq, source in group["members"]))
    return {key: group[key] for key in ("ref", "start_seq", "end_seq", "merge_mode", "supplier_id", "members")}, valid


def _group_source(group, part_no, op_type_id, suppliers):
    if group is None:
        return None, None, True
    valid = group["valid"] and group["part_no"] == part_no
    supplier = None
    if group["supplier_id"] is not None:
        supplier, supplier_valid = _supplier(suppliers, group["supplier_id"], op_type_id)
        valid = valid and supplier_valid
    return group["source_signature"], supplier, valid


def _source_facts(part, op, group, suppliers):
    group_fact, group_supplier, valid_group = _group_source(group, part["part_no"], op["op_type_id"], suppliers)
    source_valid = (op["source"] in ("internal", "external") and op["type_name"] is not None
                    and op["category"] == op["source"])
    if op["type_name"] is not None:
        _ref(op["type_ref"])
    supplier, valid_supplier = _supplier(suppliers, op["supplier_id"], op["op_type_id"])
    if op["source"] == "external":
        source_valid = source_valid and valid_supplier and valid_group and (op["ext_group_id"] is None or group is not None)
    else:
        source_valid = source_valid and op["supplier_id"] is None and op["ext_group_id"] is None
    values = [op["source"], op["op_type_id"], op["type_ref"], op["type_name"], op["category"],
              op["default_merge_mode"], op["supplier_id"], supplier, group_fact, group_supplier]
    return values, source_valid


def _valid_hours(op, group):
    if op["source"] == "internal":
        return _number(op["setup_hours"]) and _number(op["unit_hours"])
    if group and group["merge_mode"] == "merged":
        # Legacy merged groups can retain an independent per-operation duration.
        return _number(group["total_days"], positive=True) and (op["ext_days"] is None or _number(op["ext_days"], positive=True))
    return _number(op["ext_days"], positive=True)


def _operation_facts(part, op, group, suppliers):
    route = [part["ref"], _ref(op["ref"]), op["seq"], op["op_type_name"]]
    values, source_valid = _source_facts(part, op, group, suppliers)
    source = _digest(["source-v1", route, values]) if source_valid else None
    hours = _digest(["hours-v1", source, op["setup_hours"], op["unit_hours"], op["ext_days"],
                     group["total_days"] if group else None]) if source and _valid_hours(op, group) else None
    return route, {"source": source, "hours": hours}


def _load_facts(conn, part_no=None):
    """One bulk read per fact collection, regardless of the number of parts."""
    operations = _operations(conn, part_no)
    groups = _groups(conn, part_no, operations)
    suppliers = {row["supplier_id"]: dict(row, capabilities={row["op_type_id"]}) for row in _rows(conn, """
        SELECT s.supplier_id, s.op_type_id, s.status, r.ref, p.inactive_reason FROM Suppliers s
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='supplier' AND r.active=1 AND r.entity_key=s.supplier_id
        LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id""")}
    for row in _rows(conn, "SELECT supplier_id, op_type_id FROM WorkbenchSupplierOpTypes"):
        if row["supplier_id"] in suppliers:
            suppliers[row["supplier_id"]]["capabilities"].add(row["op_type_id"])
    records = _rows(conn, "SELECT c.* FROM WorkbenchProcessOperationConfirmations c" + (
        " JOIN WorkbenchEntityRefs r ON r.ref=c.part_ref WHERE r.kind='part' AND r.active=1 AND r.entity_key=?"
        if part_no is not None else ""), (part_no,) if part_no is not None else ())
    by_part, by_ref = {}, {}
    for op in operations:
        by_part.setdefault(op["part_no"], []).append(op)
    for row in records:
        by_ref.setdefault(row["part_ref"], {})[(row["operation_ref"], row["stage"])] = row
    return by_part, groups, suppliers, by_ref


def _facts(part, loaded):
    by_part, groups, suppliers, by_ref = loaded
    operations = by_part.get(part["part_no"], [])
    routes, per_op = [], {}
    for op in operations:
        route, signatures = _operation_facts(part, op, groups.get(op["ext_group_id"]), suppliers)
        routes.append(route)
        per_op[op["ref"]] = signatures
    valid_route = bool(operations) and all(type(op["seq"]) is int and op["seq"] > 0
        and isinstance(op["op_type_name"], str) and op["op_type_name"].strip() for op in operations)
    route = _digest(["route-v1", part["ref"], part["route_raw"], routes]) if valid_route else None
    signatures = {"route": route}
    previous = route
    for stage in ("source", "hours"):
        values = [[ref, signatures[stage]] for ref, signatures in per_op.items()]
        previous = _digest([stage + "-v1", previous, values]) if previous and all(value for _, value in values) else None
        signatures[stage] = previous
    return operations, signatures, per_op, by_ref.get(part["ref"], {})


def _confirmation(row, signature, prefix=""):
    valid = bool(row and signature and row[prefix + "signature"] == signature
                 and isinstance(row[prefix + "confirmed_at"], str) and row[prefix + "confirmed_at"].strip()
                 and (row[prefix + "confirmed_by"] is None or isinstance(row[prefix + "confirmed_by"], str)
                      and row[prefix + "confirmed_by"].strip()))
    return {"state": "confirmed" if valid else "unconfirmed",
            "confirmed_at": row[prefix + "confirmed_at"] if valid else None,
            "confirmed_by": row[prefix + "confirmed_by"] if valid else None}


def _operation_states(per_op, records):
    return {ref: {stage: _confirmation(records.get((ref, stage)), values[stage]) for stage in ("source", "hours")}
            for ref, values in per_op.items()}


def _legacy_view(operations):
    result = {"origin": "legacy", "stage": "source" if operations else "route", "ready": False}
    for stage, state in zip(_STAGES, ("present" if operations else "missing", "unconfirmed" if operations else "locked", "locked")):
        result[stage] = {"state": state, "confirmed_at": None, "confirmed_by": None}
    return result


def _view(stored, facts):
    operations, signatures, per_op, records = facts
    if stored is None:
        return _legacy_view(operations)
    result = {"origin": "managed", "stage": "route", "ready": False}
    op_states = _operation_states(per_op, records)
    unlocked = True
    for stage in _STAGES:
        current = _confirmation(stored, signatures[stage], stage + "_")
        complete = stage == "route" or all(row[stage]["state"] == "confirmed" for row in op_states.values())
        if not unlocked:
            current = {"state": "locked", "confirmed_at": None, "confirmed_by": None}
        elif current["state"] != "confirmed" or not complete:
            result["stage"] = stage
            current = {"state": "missing" if stage == "route" and not operations else "unconfirmed",
                       "confirmed_at": None, "confirmed_by": None}
            unlocked = False
        result[stage] = current
    if unlocked:
        result.update(stage="ready", ready=True)
    return result


def read_workflow(conn, part_no) -> dict:
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no)
        return _view(stored, _facts(part, _load_facts(conn, part_no)))


def operation_confirmations(conn, part_no) -> dict:
    with TransactionManager(conn).transaction():
        part, _ = _part(conn, part_no)
        _, _, per_op, records = _facts(part, _load_facts(conn, part_no))
        return _operation_states(per_op, records)


def workflow_snapshot(conn) -> dict:
    """Load JSON-safe workflow and per-operation states for the whole part catalog."""
    with TransactionManager(conn).transaction():
        _schema(conn)
        parts = _rows(conn, """SELECT p.*, r.ref FROM Parts p LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='part' AND r.active=1 AND r.entity_key=p.part_no ORDER BY p.part_no""")
        stored = {row["part_ref"]: row for row in _rows(conn, "SELECT * FROM WorkbenchProcessWorkflow")}
        loaded = _load_facts(conn)
        result = {}
        for part in parts:
            if not isinstance(part["part_no"], str):
                raise RuntimeError("Invalid process part number; expected text.")
            facts = _facts(part, loaded)
            result[part["part_no"]] = {"workflow": _view(stored.get(_ref(part["ref"])), facts),
                                       "operations": _operation_states(facts[2], facts[3])}
        return result


def _require_transaction(conn):
    if not conn.in_transaction:
        raise RuntimeError("Process confirmations require a caller transaction.")


def start_workflow(conn, part_no) -> dict:
    """Enroll a newly controlled template, even before any route exists."""
    _require_transaction(conn)
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no)
        if stored is None:
            conn.execute("INSERT INTO WorkbenchProcessWorkflow(part_ref) VALUES (?)", (part["ref"],))
        return read_workflow(conn, part_no)


def _save_operations(conn, part_ref, stage, per_op, records, stamp, person):
    for ref, values in per_op.items():
        old = records.get((ref, stage))
        if _confirmation(old, values[stage])["state"] == "confirmed":
            continue
        if old is None:
            conn.execute("""INSERT INTO WorkbenchProcessOperationConfirmations
                (part_ref,operation_ref,stage,signature,confirmed_at,confirmed_by) VALUES (?,?,?,?,?,?)""",
                         (part_ref, ref, stage, values[stage], stamp, person))
        else:
            conn.execute("""UPDATE WorkbenchProcessOperationConfirmations SET signature=?,confirmed_at=?,confirmed_by=?
                WHERE part_ref=? AND operation_ref=? AND stage=?""", (values[stage], stamp, person, part_ref, ref, stage))


def record_confirmation(conn, part_no, stage, confirmed_by=None) -> dict:
    """Confirm facts already written by the domain owner, atomically in its transaction."""
    _require_transaction(conn)
    if stage not in _STAGES:
        raise ValidationError("工艺确认阶段无效。", field="stage")
    if confirmed_by is not None and (not isinstance(confirmed_by, str) or not confirmed_by.strip()):
        raise ValidationError("确认人必须是真实非空名称，未知时请传 null。", field="confirmed_by")
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no)
        facts = _facts(part, _load_facts(conn, part_no))
        _, signatures, per_op, records = facts
        view = _view(stored, facts)
        previous = {"source": "route", "hours": "source"}.get(stage)
        if previous and view[previous]["state"] != "confirmed":
            raise ValidationError("请先确认上一工艺阶段的当前资料。", field="stage", details={"reason": "process_stage_locked"})
        if signatures[stage] is None:
            raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})
        if stored is None:
            conn.execute("INSERT INTO WorkbenchProcessWorkflow(part_ref) VALUES (?)", (part["ref"],))
        stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        if stage == "route":
            conn.execute("""DELETE FROM WorkbenchProcessOperationConfirmations WHERE part_ref=? AND operation_ref NOT IN (
                SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.part_no=? AND o.status='active')""",
                         (part["ref"], part_no))
        else:
            _save_operations(conn, part["ref"], stage, per_op, records, stamp, confirmed_by)
        if _confirmation(stored, signatures[stage], stage + "_")["state"] != "confirmed":
            conn.execute(f"""UPDATE WorkbenchProcessWorkflow SET {stage}_signature=?,
                {stage}_confirmed_at=?,{stage}_confirmed_by=? WHERE part_ref=?""",
                         (signatures[stage], stamp, confirmed_by, part["ref"]))
        return read_workflow(conn, part_no)


def require_template_ready(conn, part_no) -> None:
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no)
        if stored is None:
            return
        view = _view(stored, _facts(part, _load_facts(conn, part_no)))
        if not view["ready"]:
            raise BusinessError(ErrorCode.ROUTE_PARSE_ERROR, "该零件工艺尚未完成路线、归属和工时确认，不能用于创建批次工序。",
                                details={"reason": "process_workflow_pending", "stage": view["stage"]})
