"""Content-bound confirmations; reads do not create, repair or infer metadata."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.infrastructure.workbench_resource_schema import workbench_resource_contract_issues
from core.models.content import content_text, same, unpacked
from core.models.resource_capabilities import supports_source
from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository, operation_order

from .template_source import TemplateSourceFacts

_STAGES = ("route", "source", "hours")


def _schema(conn, contracts=None):
    # 逐行写入共用本命令的结构和叶子检查；独立读取使用本次请求的新实例。
    contracts = contracts if contracts is not None else schema_contract_memo(conn)
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


def _supplier(source_facts, supplier_id, op_type_id):
    row = source_facts.suppliers.get(supplier_id)
    if row is None:
        return None
    return dict(source_facts.supplier_fact(supplier_id, op_type_id), ref=_ref(row["ref"]))


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
        group["op_source_facts"] = {key: group[key] for key in ("ref", "start_seq", "end_seq", "merge_mode", "supplier_id")}
        group["source_facts"] = dict(group["op_source_facts"], members=group["members"])
        result[group["group_id"]] = group
    return result


def _group_source(group, op_type_id, source_facts):
    if group is None:
        return None, None
    supplier = None
    if group["merge_mode"] == "merged" and group["supplier_id"] is not None:
        supplier = _supplier(source_facts, group["supplier_id"], op_type_id)
    return group["op_source_facts"], supplier


def _source_facts(op, group, source_facts):
    group_fact, group_supplier = _group_source(group, op["op_type_id"], source_facts)
    if op["type_name"] is not None:
        _ref(op["type_ref"])
    supplier = _supplier(source_facts, op["supplier_id"], op["op_type_id"])
    source_valid = not source_facts.issues(op, type_name=op["type_name"], category=op["category"])
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


def _operation_facts(part, op, group, source_facts, *, need_source, need_hours):
    route = [part["ref"], _ref(op["ref"]), op["seq"], op["op_type_name"]]
    if not need_source:
        if op["type_name"] is not None:
            _ref(op["type_ref"])
        source = None
        hours = None
    else:
        values, source_valid = _source_facts(op, group, source_facts)
        source = _source_content(route, values, source_valid)
        hours = _hours_content(source, op, group) if need_hours else None
    return route, {"source": source, "hours": hours,
                   "group": group["source_facts"] if group else None}


def _sync_cross_part_groups(cross_part_by_group, part_no, part_ops, old_operations):
    """该零件在跨件分组索引里的成员换成当前工序：旧工序和新工序涉及的分组都先清掉它的旧成员。"""
    if cross_part_by_group is None:
        return
    touched = {op["ext_group_id"] for op in (*old_operations, *part_ops) if op["ext_group_id"] is not None}
    for gid in touched:
        cross_part_by_group[gid] = [item for item in cross_part_by_group.get(gid, ()) if item["part_no"] != part_no]
    for op in part_ops:
        if op["ext_group_id"] is not None:
            cross_part_by_group.setdefault(op["ext_group_id"], []).append(op)


def _stage_confirmed(stored, field):
    return stored is not None and bool(stored[field])


def _needed_stages(stored, stage, record_stages):
    need_hours = stage == "hours" or _stage_confirmed(stored, "hours_confirmed_at") or ("hours" in record_stages)
    need_source = (need_hours or stage == "source"
                   or _stage_confirmed(stored, "source_confirmed_at") or ("source" in record_stages))
    need_route = need_source or stage == "route" or _stage_confirmed(stored, "route_confirmed_at")
    return need_route, need_source, need_hours


def _load_facts(conn, part_no=None, *, stored=None, stage=None, cross_part_by_group=None, old_operations=()):
    """One bulk read per fact collection, regardless of the number of parts."""
    return _project_facts(_read_facts(conn, part_no, stored=stored, stage=stage,
                                      cross_part_by_group=cross_part_by_group, old_operations=old_operations))


def _read_part_source_facts(repo, part_no, cross_part_by_group, old_operations):
    if cross_part_by_group is None:
        operations = repo.active_operations(part_no, include_related_groups=True)
        groups = (repo.active_external_groups(part_no)
                  if any(op["ext_group_id"] is not None for op in operations) else [])
        return operations, groups
    part_ops = repo.active_operations(part_no, include_related_groups=False)
    _sync_cross_part_groups(cross_part_by_group, part_no, part_ops, old_operations)
    if not part_ops:
        return [], []
    group_ids = {op["ext_group_id"] for op in part_ops if op["ext_group_id"] is not None}
    groups = repo.active_external_groups(part_no) if group_ids else []
    group_ids.update(group["group_id"] for group in groups)
    cross_ops = [op for gid in group_ids for op in cross_part_by_group.get(gid, ()) if op["part_no"] != part_no]
    operations = sorted(part_ops + cross_ops, key=operation_order) if cross_ops else part_ops
    return operations, groups


def _read_facts(conn, part_no=None, *, stored=None, stage=None, cross_part_by_group=None, old_operations=()):
    repo = WorkbenchProcessWorkflowRepository(conn)
    if part_no is None:
        return {"operations": repo.active_operations(), "groups": repo.active_external_groups(),
                "suppliers": repo.supplier_facts(None), "capabilities": repo.supplier_op_types(None),
                "records": repo.confirmations()}
    records = repo.confirmations(part_no)
    need_source = _needed_stages(stored, stage, {row["stage"] for row in records})[1]
    if not need_source:
        operations = repo.active_operations(part_no, include_related_groups=False)
        _sync_cross_part_groups(cross_part_by_group, part_no, operations, old_operations)
        return {"operations": operations, "groups": [], "suppliers": [], "capabilities": [], "records": records}
    operations, groups = _read_part_source_facts(repo, part_no, cross_part_by_group, old_operations)
    if not operations:
        return {"operations": [], "groups": [], "suppliers": [], "capabilities": [], "records": []}
    supplier_ids = list(dict.fromkeys(
        row["supplier_id"] for rows in (operations, groups) for row in rows if row["supplier_id"] is not None))
    return {"operations": operations, "groups": groups,
            "suppliers": repo.supplier_facts(supplier_ids), "capabilities": repo.supplier_op_types(supplier_ids),
            "records": records}


def _project_facts(raw):
    operations = raw["operations"]
    groups = _groups(raw["groups"], operations)
    source_facts = TemplateSourceFacts(operations, groups.values(), raw["suppliers"],
                                      raw["capabilities"], raw["suppliers"])
    records = raw["records"]
    by_part, by_ref = {}, {}
    for op in operations:
        by_part.setdefault(op["part_no"], []).append(op)
    for row in records:
        by_ref.setdefault(row["part_ref"], {})[(row["operation_ref"], row["stage"])] = row
    return by_part, groups, source_facts, by_ref


def _valid_route_operation(op):
    return (type(op["seq"]) is int and op["seq"] > 0
            and isinstance(op["op_type_name"], str) and bool(op["op_type_name"].strip()))


def _stage_document(name, previous, per_op, group_facts):
    values = [[ref, item[name]] for ref, item in per_op.items()]
    document = [name + "-v2", previous, values]
    if name == "source":
        document.append(group_facts)
    return content_text(document) if previous and all(value is not None for _, value in values) else None


def _facts(part, loaded, stored=None, *, stage=None):
    by_part, groups, suppliers, by_ref = loaded
    operations = by_part.get(part["part_no"], [])
    records = by_ref.get(part["ref"], {})
    need_route, need_source, need_hours = _needed_stages(stored, stage, {rec_stage for _, rec_stage in records})
    routes, per_op, group_facts = [], {}, {}
    for op in operations:
        route, contents = _operation_facts(part, op, groups.get(op["ext_group_id"]), suppliers,
                                           need_source=need_source, need_hours=need_hours)
        routes.append(route)
        per_op[op["ref"]] = contents
        if contents["group"] is not None:
            group_facts[contents["group"]["ref"]] = contents["group"]
    valid_route = bool(operations) and all(_valid_route_operation(op) for op in operations)
    route = content_text(["route-v2", part["ref"], part["route_raw"], routes]) if need_route and valid_route else None
    source = _stage_document("source", route, per_op, group_facts) if need_source else None
    hours = _stage_document("hours", source, per_op, group_facts) if need_hours else None
    return operations, {"route": route, "source": source, "hours": hours}, per_op, records


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


def _view(stored, facts, *, operation_states=None):
    operations, contents, per_op, records = facts
    if stored is None:
        return _legacy_view(operations)
    result = {"origin": "managed", "stage": "route", "ready": False}
    op_states = _operation_states(per_op, records, stored) if operation_states is None else operation_states
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


def workflow_snapshot(conn, *, tables=None, identities=None) -> dict:
    """Load JSON-safe workflow and per-operation states for the whole part catalog."""
    if tables is not None and conn.in_transaction:
        _schema(conn)
        raw = _workflow_inputs_from_tables(tables, identities, conn=conn)
    else:
        with TransactionManager(conn).transaction():
            if tables is None:
                raw = load_workflow_snapshot(conn)
            else:
                _schema(conn)
                raw = _workflow_inputs_from_tables(tables, identities, conn=conn)
    return project_workflow_snapshot(raw)


def _active_refs(tables, identities):
    if identities is not None:
        return {key: row["ref"] for key, row in identities.items()}
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}


def _workflow_inputs_from_tables(tables, identities, *, conn):
    """Join the caller's captured raw collections; do not read a second catalog."""
    repo = WorkbenchProcessWorkflowRepository(conn)
    stored = (tables["WorkbenchProcessWorkflow"]
              if "WorkbenchProcessWorkflow" in tables else repo.stored_workflows())
    records = (tables["WorkbenchProcessOperationConfirmations"]
               if "WorkbenchProcessOperationConfirmations" in tables else repo.confirmations())
    refs = _active_refs(tables, identities)
    types = {row["op_type_id"]: row for row in tables["OpTypes"]}
    profiles = {row["supplier_id"]: row for row in tables["WorkbenchSupplierProfiles"]}
    operations = []
    for row in tables["PartOperations"]:
        if row["status"] != "active":
            continue
        kind = types.get(row["op_type_id"], {})
        operations.append(dict(row, ref=refs.get(("template_operation", str(row["id"]))),
            type_name=kind.get("name"), category=kind.get("category"),
            type_ref=refs.get(("op_type", row["op_type_id"]))))
    operations.sort(key=operation_order)
    used = {row["ext_group_id"] for row in operations if row["ext_group_id"] is not None}
    return {"parts": [dict(row, ref=refs.get(("part", row["part_no"]))) for row in tables["Parts"]],
            "stored": stored, "facts": {
                "operations": operations,
                "groups": [dict(row, ref=refs.get(("template_external_group", row["group_id"])))
                           for row in tables["ExternalGroups"] if row["group_id"] in used],
                "suppliers": [dict(row, ref=refs.get(("supplier", row["supplier_id"])),
                                   inactive_reason=profiles.get(row["supplier_id"], {}).get("inactive_reason"))
                              for row in tables["Suppliers"]],
                "capabilities": tables["WorkbenchSupplierOpTypes"],
                "records": records}}


def load_workflow_snapshot(conn, *, tables=None) -> dict:
    """Capture stored inputs; callers own the encompassing read transaction."""
    _require_transaction(conn)
    _schema(conn)
    if tables is not None:
        return _workflow_inputs_from_tables(tables, None, conn=conn)
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
        original = stored.get(_ref(part["ref"]))
        facts = _facts(part, loaded, original)
        op_states = _operation_states(facts[2], facts[3], original)
        result[part["part_no"]] = {"workflow": _view(original, facts, operation_states=op_states),
                                   "operations": op_states}
    return result


def _require_transaction(conn):
    if not conn.in_transaction:
        raise RuntimeError("Process confirmations require a caller transaction.")


def start_workflow(conn, part_no, *, contracts=None) -> dict:
    """Enroll a newly controlled template, even before any route exists."""
    _require_transaction(conn)
    part, stored = _part(conn, part_no, contracts)
    if stored is None:
        WorkbenchProcessWorkflowRepository(conn).insert_workflow(part["ref"])
        stored = {stage + "_" + key: None for stage in _STAGES for key in ("signature", "content_json", "confirmed_at", "confirmed_by")}
    return _view(stored, _facts(part, _load_facts(conn, part_no, stored=stored), stored))


def _save_operations(conn, part_ref, stage, per_op, records, states, stamp):
    repo = WorkbenchProcessWorkflowRepository(conn)
    for ref, values in per_op.items():
        old = records.get((ref, stage))
        if states[ref][stage]["state"] == "confirmed":
            continue
        if old is None:
            repo.insert_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, content_json=values[stage],
                                     confirmed_at=stamp)
        else:
            repo.update_confirmation(part_ref=part_ref, operation_ref=ref, stage=stage, content_json=values[stage],
                                     confirmed_at=stamp)
        records[(ref, stage)] = {"signature": old.get("signature") if old else None, "content_json": values[stage],
                                "confirmed_at": stamp, "confirmed_by": None}


def record_confirmation(conn, part_no, stage, *, contracts=None, cross_part_by_group=None, old_operations=()) -> dict:
    """Confirm facts already written by the domain owner, atomically in its transaction.

    cross_part_by_group 是多零件命令共用的跨件分组索引；换掉路线时 old_operations 传该零件换路线前的工序，
    索引里旧工序所在分组的旧成员在这里一起清掉。
    """
    _require_transaction(conn)
    if stage not in _STAGES:
        raise ValidationError("工艺确认阶段无效。", field="stage")
    part, stored = _part(conn, part_no, contracts)
    facts = _facts(
        part,
        _load_facts(conn, part_no, stored=stored, stage=stage, cross_part_by_group=cross_part_by_group,
                    old_operations=old_operations),
        stored,
        stage=stage,
    )
    _, contents, per_op, records = facts
    op_states = _operation_states(per_op, records, stored) if stored is not None else None
    view = _view(stored, facts, operation_states=op_states)
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
        _save_operations(conn, part["ref"], stage, per_op, records, op_states, stamp)
    if _confirmation(stored, content, stage + "_")["state"] != "confirmed":
        repo.set_stage_confirmation(part_ref=part["ref"], stage=stage, content_json=content, confirmed_at=stamp)
        stored = dict(stored, **{stage + "_content_json": content, stage + "_confirmed_at": stamp,
                                 stage + "_confirmed_by": None})
    # 路线确认不改工序确认记录和来源资料，沿用上面算好的工序状态；来源、工时确认刚写了记录，要重算。
    return _view(stored, facts, operation_states=op_states if stage == "route" else None)
