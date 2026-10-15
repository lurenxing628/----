"""Content-bound confirmations; reads do not create, repair or infer metadata."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.connection_guards import SchemaContractMemo
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.infrastructure.workbench_resource_schema import workbench_resource_contract_issues
from core.models.content import content_text, same, unpacked
from core.models.resource_capabilities import supports_source
from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository

from .template_source import source_issues, valid_external_group, valid_supplier

_STAGES = ("route", "source", "hours")


def _schema(conn, contracts=None):
    # 逐行写入共用本命令的结构和叶子检查；独立读取使用本次请求的新实例。
    contracts = contracts if contracts is not None else SchemaContractMemo(conn)
    issues = (contracts.get_schema(workbench_metadata_contract_issues)
              + contracts.get_schema(workbench_resource_contract_issues)
              + contracts.get_schema(workbench_process_contract_issues)
              + contracts.get_schema(workbench_process_workflow_contract_issues))
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
        # Store membership once in the part's source document. Each operation
        # owns its supplier facts and refers to this shared group evidence.
        group["members"] = [[op["ref"], op["seq"], op["source"]] for op in current]
        fact, valid = _group_facts(group, group["part_no"],
            [(op["seq"], op["source"], op["supplier_id"]) for op in current])
        group["source_facts"], group["valid"] = fact, valid
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
    return {key: value for key, value in group["source_facts"].items() if key != "members"}, supplier, valid


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


def _source_content(route, values, source_valid):
    return content_text(["source-v2", route, values]) if source_valid else None


def _hours_content(source, op, group):
    """Only effective hours and cycles belong to the current confirmation."""
    merged = group is not None and group["merge_mode"] == "merged"
    return content_text(["hours-v2", source, op["setup_hours"], op["unit_hours"], None if merged else op["ext_days"],
                         group["total_days"] if group else None]) if source and _valid_hours(op, group) else None


def _operation_facts(part, op, group, suppliers):
    route = [part["ref"], _ref(op["ref"]), op["seq"], op["op_type_name"]]
    values, source_valid = _source_facts(part, op, group, suppliers)
    source = _source_content(route, values, source_valid)
    hours = _hours_content(source, op, group)
    return route, {"source": source, "hours": hours,
                   "group": group["source_facts"] if group else None}


def _load_facts(conn, part_no=None):
    """One bulk read per fact collection, regardless of the number of parts."""
    return _project_facts(_read_facts(conn, part_no))


def _read_facts(conn, part_no=None):
    repo = WorkbenchProcessWorkflowRepository(conn)
    operations, groups = repo.active_operations(part_no), repo.active_external_groups(part_no)
    supplier_ids = None if part_no is None else list(dict.fromkeys(
        row["supplier_id"] for rows in (operations, groups) for row in rows if row["supplier_id"] is not None))
    return {"operations": operations, "groups": groups,
            "suppliers": repo.supplier_facts(supplier_ids), "capabilities": repo.supplier_op_types(supplier_ids),
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
    routes, per_op, group_facts = [], {}, {}
    for op in operations:
        route, contents = _operation_facts(part, op, groups.get(op["ext_group_id"]), suppliers)
        routes.append(route)
        per_op[op["ref"]] = contents
        if contents["group"] is not None:
            group_facts[contents["group"]["ref"]] = contents["group"]
    valid_route = bool(operations) and all(type(op["seq"]) is int and op["seq"] > 0
        and isinstance(op["op_type_name"], str) and op["op_type_name"].strip() for op in operations)
    route = content_text(["route-v2", part["ref"], part["route_raw"], routes]) if valid_route else None
    contents = {"route": route}
    previous = route
    for stage in ("source", "hours"):
        values = [[ref, item[stage]] for ref, item in per_op.items()]
        document = [stage + "-v2", previous, values]
        if stage == "source":
            document.append(group_facts)
        previous = content_text(document) if previous and all(value is not None for _, value in values) else None
        contents[stage] = previous
    return operations, contents, per_op, records


def _confirmation(row, content, prefix="", *, missing_original=False):
    recorded = bool(row and isinstance(row.get(prefix + "confirmed_at"), str) and row[prefix + "confirmed_at"].strip()
                    and (row.get(prefix + "confirmed_by") is None or isinstance(row[prefix + "confirmed_by"], str)
                         and row[prefix + "confirmed_by"].strip()))
    saved = row.get(prefix + "content_json") if row else None
    valid = bool(recorded and content is not None and saved == content)
    result = {"state": "confirmed" if valid else "unconfirmed",
            "confirmed_at": row[prefix + "confirmed_at"] if valid else None,
            "confirmed_by": row[prefix + "confirmed_by"] if valid else None}
    if recorded and (saved is None or missing_original):
        result.update(history={"confirmed_at": row[prefix + "confirmed_at"], "confirmed_by": row[prefix + "confirmed_by"]},
                      content_state="missing_original", reason="历史确认缺少当时的工艺资料，请重新确认当前资料。")
    return result


def _saved_groups(stored):
    saved = stored.get("source_content_json") if stored else None
    if saved is None:
        return None
    try:
        document = unpacked(json.loads(saved))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid saved process source content.") from exc
    if type(document) is not list or len(document) != 4 or document[0] != "source-v2" or type(document[3]) is not dict:
        raise RuntimeError("Invalid saved process source content.")
    return document[3]


def _operation_states(per_op, records, stored=None):
    saved_groups, group_matches, result = _saved_groups(stored), {}, {}
    for ref, values in per_op.items():
        group = values["group"]
        if group is not None and group["ref"] not in group_matches:
            original = saved_groups.get(group["ref"]) if saved_groups is not None else None
            group_matches[group["ref"]] = (original is not None and same(original, group), original is None)
        matching, missing = (True, False) if group is None else group_matches[group["ref"]]
        result[ref] = {stage: _confirmation(records.get((ref, stage)), values[stage] if matching else None,
                                          missing_original=missing)
                       for stage in ("source", "hours")}
    return result


def _legacy_view(operations):
    result = {"origin": "legacy", "stage": "source" if operations else "route", "ready": False}
    for stage, state in zip(_STAGES, ("present" if operations else "missing", "unconfirmed" if operations else "locked", "locked")):
        result[stage] = {"state": state, "confirmed_at": None, "confirmed_by": None}
    return result


def _view(stored, facts):
    operations, contents, per_op, records = facts
    if stored is None:
        return _legacy_view(operations)
    result = {"origin": "managed", "stage": "route", "ready": False}
    op_states = _operation_states(per_op, records, stored)
    unlocked = True
    for stage in _STAGES:
        current = _confirmation(stored, contents[stage], stage + "_")
        complete = stage == "route" or all(row[stage]["state"] == "confirmed" for row in op_states.values())
        if not unlocked:
            current = dict(current, state="locked", confirmed_at=None, confirmed_by=None)
        elif current["state"] != "confirmed" or not complete:
            result["stage"] = stage
            current = dict(current, state="missing" if stage == "route" and not operations else "unconfirmed",
                           confirmed_at=None, confirmed_by=None)
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
        part, stored = _part(conn, part_no)
        _, _, per_op, records = _facts(part, _load_facts(conn, part_no))
        return _operation_states(per_op, records, stored)


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
        original = stored.get(_ref(part["ref"]))
        result[part["part_no"]] = {"workflow": _view(original, facts),
                                   "operations": _operation_states(facts[2], facts[3], original)}
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
            stored = {stage + "_" + key: None for stage in _STAGES for key in ("signature", "content_json", "confirmed_at", "confirmed_by")}
        return _view(stored, _facts(part, _load_facts(conn, part_no)))


def _save_operations(conn, part_ref, stage, per_op, records, stored, stamp, person):
    repo = WorkbenchProcessWorkflowRepository(conn)
    states = _operation_states(per_op, records, stored)
    for ref, values in per_op.items():
        old = records.get((ref, stage))
        if states[ref][stage]["state"] == "confirmed":
            continue
        if old is None:
            repo.insert_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, content_json=values[stage],
                                     confirmed_at=stamp, confirmed_by=person)
        else:
            repo.update_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, content_json=values[stage],
                                     confirmed_at=stamp, confirmed_by=person)
        records[(ref, stage)] = {"signature": old.get("signature") if old else None, "content_json": values[stage],
                                "confirmed_at": stamp, "confirmed_by": person}


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
        _, contents, per_op, records = facts
        view = _view(stored, facts)
        previous = {"source": "route", "hours": "source"}.get(stage)
        if previous and view[previous]["state"] != "confirmed":
            raise ValidationError("请先确认上一工艺阶段的当前资料。", field="stage", details={"reason": "process_stage_locked"})
        content = contents[stage]
        if content is None:
            raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})
        repo = WorkbenchProcessWorkflowRepository(conn)
        if stored is None:
            repo.insert_workflow(part["ref"])
            stored = {name + "_" + key: None for name in _STAGES for key in ("signature", "content_json", "confirmed_at", "confirmed_by")}
        stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        if stage == "route":
            repo.delete_confirmations_outside_active_route(part["ref"], part_no)
        else:
            _save_operations(conn, part["ref"], stage, per_op, records, stored, stamp, confirmed_by)
        if _confirmation(stored, content, stage + "_")["state"] != "confirmed":
            repo.set_stage_confirmation(part_ref=part["ref"], stage=stage, content_json=content,
                                        confirmed_at=stamp, confirmed_by=confirmed_by)
            stored = dict(stored, **{stage + "_content_json": content, stage + "_confirmed_at": stamp,
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
