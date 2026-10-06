"""Content-bound confirmations; reads do not create, repair or infer metadata."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.infrastructure.workbench_resource_schema import workbench_resource_contract_issues
from core.models.resource_capabilities import supports_source
from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository

from .template_source import source_issues, valid_external_group, valid_supplier

_STAGES = ("route", "source", "hours")


def _schema_issues(conn):
    return tuple(workbench_metadata_contract_issues(conn) + workbench_resource_contract_issues(conn)
                 + workbench_process_contract_issues(conn) + workbench_process_workflow_contract_issues(conn))


def _schema(conn, contracts=None):
    # contracts（SchemaContractMemo）由逐行写入的调用方传入：同一命令里表结构只解析一次，改过就重验。
    issues = _schema_issues(conn) if contracts is None else contracts.get(_schema_issues)
    if issues:
        raise RuntimeError("Invalid process workflow storage: " + "; ".join(issues))


def _ref(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise RuntimeError("Missing process workflow entity identity; no metadata was repaired.")
    return value


def _part(conn, part_no, contracts=None):
    _schema(conn, contracts)
    repo = WorkbenchProcessWorkflowRepository(conn)
    rows = repo.part_with_ref(part_no)
    if not rows:
        raise BusinessError(ErrorCode.PART_NOT_FOUND, "零件不存在。")
    part = rows[0]
    _ref(part["ref"])
    stored = repo.stored_workflow(part["ref"])
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
    return fact, valid_supplier(fact)


def _groups(groups, operations):
    members = {}
    for op in operations:
        members.setdefault((op["part_no"], op["ext_group_id"]), []).append(op)
    result = {}
    for group in groups:
        _ref(group["ref"])
        current = members.get((group["part_no"], group["group_id"]), [])
        # Keep the persisted confirmation signature shape. Each operation's source
        # signature already owns its supplier; validation also needs the full set.
        group["members"] = [[op["ref"], op["seq"], op["source"]] for op in current]
        fact, valid = _group_facts(group, group["part_no"],
            [(op["seq"], op["source"], op["supplier_id"]) for op in current])
        group["source_signature"], group["valid"] = _digest(fact), valid
        result[group["group_id"]] = group
    return result


def _group_facts(group, part_no, members):
    if group is None:
        return None, True
    valid = valid_external_group(group, part_no, members)
    return {key: group[key] for key in ("ref", "start_seq", "end_seq", "merge_mode", "supplier_id", "members")}, valid


def _group_source(group, part_no, op_type_id, suppliers):
    if group is None:
        return None, None, True
    valid = group["valid"] and group["part_no"] == part_no
    supplier = None
    if group["merge_mode"] == "merged" and group["supplier_id"] is not None:
        supplier, supplier_valid = _supplier(suppliers, group["supplier_id"], op_type_id)
        valid = valid and supplier_valid
    return group["source_signature"], supplier, valid


def _source_facts(part, op, group, suppliers):
    group_fact, group_supplier, valid_group = _group_source(group, part["part_no"], op["op_type_id"], suppliers)
    if op["type_name"] is not None:
        _ref(op["type_ref"])
    supplier, valid_supplier = _supplier(suppliers, op["supplier_id"], op["op_type_id"])
    source_valid = not source_issues(op, type_name=op["type_name"], category=op["category"],
                                    supplier_valid=valid_supplier, group=group, group_valid=valid_group)
    # This slot used to contain the resource's default policy. Defaults only seed
    # new groups; the actual group facts above govern existing confirmations.
    values = [op["source"], op["op_type_id"], op["type_ref"], op["type_name"], op["source"] if supports_source(op["category"], op["source"]) else op["category"],
              None, op["supplier_id"], supplier, group_fact, group_supplier]
    return values, source_valid


def _valid_hours(op, group):
    if op["source"] == "internal":
        return _number(op["setup_hours"]) and _number(op["unit_hours"])
    if group and group["merge_mode"] == "merged":
        # A merged group owns the duration. Retained per-operation history is not
        # an effective cycle and must not prevent confirming its valid total.
        return _number(group["total_days"], positive=True)
    return _number(op["ext_days"], positive=True)


def _legacy_separate_supplier(group, suppliers):
    """Old confirmations only admitted an active, capable group supplier."""
    if group is None or group["merge_mode"] != "separate" or group["supplier_id"] is None:
        return None
    supplier = suppliers.get(group["supplier_id"])
    if supplier is None:
        return None
    # Retain the former signature encoding, without consulting this unused
    # supplier's present qualification. The declared group identity still matches.
    return {"ref": _ref(supplier["ref"]), "status": "active", "inactive_reason": None, "capable": True}


def _source_signature(route, values, source_valid, old, legacy_group_supplier=None):
    """Verify actual source facts and recognize equivalent prior encodings."""
    source = _digest(["source-v1", route, values]) if source_valid else None
    if source and old is not None and old["signature"] != source:
        variants = [values]
        if legacy_group_supplier is not None:
            variants.append(values[:-1] + [legacy_group_supplier])
        # Actual member suppliers and the declared group facts must still match.
        # Only retired default/unused qualification slots may use the old encoding.
        for candidate in variants:
            for mode in (None, "separate", "merged"):
                legacy = _digest(["source-v1", route, candidate[:5] + [mode] + candidate[6:]])
                if old["signature"] == legacy:
                    return legacy
    return source


def _hours_signature(source, op, group, old_hours):
    """Use effective hours while recognizing equivalent historical signatures."""
    merged = group is not None and group["merge_mode"] == "merged"
    hours = _digest(["hours-v1", source, op["setup_hours"], op["unit_hours"], None if merged else op["ext_days"],
                     group["total_days"] if group else None]) if source and _valid_hours(op, group) else None
    if hours and group is not None and group["merge_mode"] == "merged" and old_hours is not None and old_hours["signature"] != hours:
        legacy = _digest(["hours-v1", source, op["setup_hours"], op["unit_hours"], op["ext_days"], group["total_days"]])
        if old_hours["signature"] == legacy:
            hours = legacy
    return hours


def _operation_facts(part, op, group, suppliers, records):
    route = [part["ref"], _ref(op["ref"]), op["seq"], op["op_type_name"]]
    values, source_valid = _source_facts(part, op, group, suppliers)
    source = _source_signature(route, values, source_valid, records.get((op["ref"], "source")),
                               _legacy_separate_supplier(group, suppliers))
    hours = _hours_signature(source, op, group, records.get((op["ref"], "hours")))
    return route, {"source": source, "hours": hours}


def _load_facts(conn, part_no=None):
    """One bulk read per fact collection, regardless of the number of parts."""
    return _project_facts(_read_facts(conn, part_no))


def _read_facts(conn, part_no=None):
    repo = WorkbenchProcessWorkflowRepository(conn)
    return {"operations": repo.active_operations(part_no), "groups": repo.active_external_groups(part_no),
            "suppliers": repo.supplier_facts(), "capabilities": repo.supplier_op_types(),
            "records": repo.confirmations(part_no)}


def _project_facts(raw):
    operations = raw["operations"]
    groups = _groups([dict(row) for row in raw["groups"]], operations)
    suppliers = {row["supplier_id"]: dict(row, capabilities={row["op_type_id"]}) for row in raw["suppliers"]}
    for row in raw["capabilities"]:
        if row["supplier_id"] in suppliers:
            suppliers[row["supplier_id"]]["capabilities"].add(row["op_type_id"])
    records = raw["records"]
    by_part, by_ref = {}, {}
    for op in operations:
        by_part.setdefault(op["part_no"], []).append(op)
    for row in records:
        by_ref.setdefault(row["part_ref"], {})[(row["operation_ref"], row["stage"])] = row
    return by_part, groups, suppliers, by_ref


def _facts(part, loaded):
    by_part, groups, suppliers, by_ref = loaded
    operations = by_part.get(part["part_no"], [])
    records = by_ref.get(part["ref"], {})
    routes, per_op = [], {}
    for op in operations:
        route, signatures = _operation_facts(part, op, groups.get(op["ext_group_id"]), suppliers, records)
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
    return operations, signatures, per_op, records


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


def read_workflow(conn, part_no, *, contracts=None) -> dict:
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no, contracts)
        return _view(stored, _facts(part, _load_facts(conn, part_no)))


def operation_confirmations(conn, part_no) -> dict:
    with TransactionManager(conn).transaction():
        part, _ = _part(conn, part_no)
        _, _, per_op, records = _facts(part, _load_facts(conn, part_no))
        return _operation_states(per_op, records)


def workflow_snapshot(conn, *, tables=None) -> dict:
    """Load JSON-safe workflow and per-operation states for the whole part catalog."""
    with TransactionManager(conn).transaction():
        if tables is None:
            raw = load_workflow_snapshot(conn)
        else:
            _schema(conn)
            raw = _workflow_inputs_from_tables(tables)
    return project_workflow_snapshot(raw)


def _workflow_inputs_from_tables(tables):
    """Join the caller's captured raw collections; do not read a second catalog."""
    refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    types = {row["op_type_id"]: row for row in tables["OpTypes"]}
    policies = {row["op_type_id"]: row for row in tables["WorkbenchOpTypePolicies"]}
    profiles = {row["supplier_id"]: row for row in tables["WorkbenchSupplierProfiles"]}
    operations = []
    for row in tables["PartOperations"]:
        if row["status"] != "active":
            continue
        kind = types.get(row["op_type_id"], {})
        operations.append(dict(row, ref=refs.get(("template_operation", str(row["id"]))),
            type_name=kind.get("name"), category=kind.get("category"),
            type_ref=refs.get(("op_type", row["op_type_id"])),
            default_merge_mode=policies.get(row["op_type_id"], {}).get("default_merge_mode")))
    def sql_order(value):
        if value is None:
            return (0, "")
        if isinstance(value, (int, float)):
            return (1, value)
        return (2 if isinstance(value, str) else 3, value)
    operations.sort(key=lambda row: tuple(sql_order(row[key]) for key in ("part_no", "seq", "id")))
    used = {row["ext_group_id"] for row in operations if row["ext_group_id"] is not None}
    return {"parts": [dict(row, ref=refs.get(("part", row["part_no"]))) for row in tables["Parts"]],
            "stored": tables["WorkbenchProcessWorkflow"], "facts": {
                "operations": operations,
                "groups": [dict(row, ref=refs.get(("template_external_group", row["group_id"])))
                           for row in tables["ExternalGroups"] if row["group_id"] in used],
                "suppliers": [dict(row, ref=refs.get(("supplier", row["supplier_id"])),
                                   inactive_reason=profiles.get(row["supplier_id"], {}).get("inactive_reason"))
                              for row in tables["Suppliers"]],
                "capabilities": tables["WorkbenchSupplierOpTypes"],
                "records": tables["WorkbenchProcessOperationConfirmations"]}}


def load_workflow_snapshot(conn) -> dict:
    """Capture stored inputs; callers own the encompassing read transaction."""
    _require_transaction(conn)
    _schema(conn)
    repo = WorkbenchProcessWorkflowRepository(conn)
    return {"parts": repo.parts_with_refs(), "stored": repo.stored_workflows(), "facts": _read_facts(conn)}


def project_workflow_snapshot(raw) -> dict:
    """Project a captured catalog without retaining a SQLite read lock."""
    stored = {row["part_ref"]: row for row in raw["stored"]}
    loaded = _project_facts(raw["facts"])
    result = {}
    for part in raw["parts"]:
        if not isinstance(part["part_no"], str):
            raise RuntimeError("Invalid process part number; expected text.")
        facts = _facts(part, loaded)
        result[part["part_no"]] = {"workflow": _view(stored.get(_ref(part["ref"])), facts),
                                   "operations": _operation_states(facts[2], facts[3])}
    return result


def _require_transaction(conn):
    if not conn.in_transaction:
        raise RuntimeError("Process confirmations require a caller transaction.")


def start_workflow(conn, part_no, *, contracts=None) -> dict:
    """Enroll a newly controlled template, even before any route exists."""
    _require_transaction(conn)
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no, contracts)
        if stored is None:
            WorkbenchProcessWorkflowRepository(conn).insert_workflow(part["ref"])
            stored = {stage + "_" + key: None for stage in _STAGES for key in ("signature", "confirmed_at", "confirmed_by")}
        return _view(stored, _facts(part, _load_facts(conn, part_no)))


def _save_operations(conn, part_ref, stage, per_op, records, stamp, person):
    repo = WorkbenchProcessWorkflowRepository(conn)
    for ref, values in per_op.items():
        old = records.get((ref, stage))
        if _confirmation(old, values[stage])["state"] == "confirmed":
            continue
        if old is None:
            repo.insert_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, signature=values[stage],
                                     confirmed_at=stamp, confirmed_by=person)
        else:
            repo.update_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, signature=values[stage],
                                     confirmed_at=stamp, confirmed_by=person)
        records[(ref, stage)] = {"signature": values[stage], "confirmed_at": stamp, "confirmed_by": person}


def record_confirmation(conn, part_no, stage, confirmed_by=None, *, contracts=None) -> dict:
    """Confirm facts already written by the domain owner, atomically in its transaction."""
    _require_transaction(conn)
    if stage not in _STAGES:
        raise ValidationError("工艺确认阶段无效。", field="stage")
    if confirmed_by is not None and (not isinstance(confirmed_by, str) or not confirmed_by.strip()):
        raise ValidationError("确认人必须是真实非空名称，未知时请传 null。", field="confirmed_by")
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no, contracts)
        facts = _facts(part, _load_facts(conn, part_no))
        _, signatures, per_op, records = facts
        view = _view(stored, facts)
        previous = {"source": "route", "hours": "source"}.get(stage)
        if previous and view[previous]["state"] != "confirmed":
            raise ValidationError("请先确认上一工艺阶段的当前资料。", field="stage", details={"reason": "process_stage_locked"})
        signature = signatures[stage]
        if signature is None:
            raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})
        repo = WorkbenchProcessWorkflowRepository(conn)
        if stored is None:
            repo.insert_workflow(part["ref"])
            stored = {name + "_" + key: None for name in _STAGES for key in ("signature", "confirmed_at", "confirmed_by")}
        stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        if stage == "route":
            repo.delete_confirmations_outside_active_route(part["ref"], part_no)
        else:
            _save_operations(conn, part["ref"], stage, per_op, records, stamp, confirmed_by)
        if _confirmation(stored, signature, stage + "_")["state"] != "confirmed":
            repo.set_stage_confirmation(part_ref=part["ref"], stage=stage, signature=signature,
                                        confirmed_at=stamp, confirmed_by=confirmed_by)
            stored = dict(stored, **{stage + "_signature": signature, stage + "_confirmed_at": stamp,
                                     stage + "_confirmed_by": confirmed_by})
        return _view(stored, facts)


def require_template_ready(conn, part_no) -> None:
    with TransactionManager(conn).transaction():
        part, stored = _part(conn, part_no)
        if stored is None:
            return
        view = _view(stored, _facts(part, _load_facts(conn, part_no)))
        if not view["ready"]:
            raise BusinessError(ErrorCode.ROUTE_PARSE_ERROR, "该零件工艺尚未完成路线、归属和工时确认，不能用于生成批次工序。",
                                details={"reason": "process_workflow_pending", "stage": view["stage"]})
