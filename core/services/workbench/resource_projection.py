"""Public entity fields are explicitly selected from private raw state."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_supplier import supplier_state
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService


def _related(value):
    if value is None:
        return None
    return {"ref": value["identity"]["ref"], "business_code": value["identity"]["entity_key"], "label": value["record"]["name"]}


def _operator_status(raw, profile):
    if raw["status"] == "active":
        return "active"
    if raw["status"] == "inactive" and profile:
        return {"leave": "leave", "disabled": "inactive"}.get(profile["inactive_reason"], "unknown")
    return "unknown"


def project_resource(kind, identity, state, *, availability=None, availability_issues=()):
    raw = state["supplier"] if kind == "supplier" else state["record"]
    entity = {"ref": identity.ref, "business_code": identity.entity_key, "label": raw["name"],
              "status": raw.get("status"), "fields": {"remark": raw.get("remark")}, "relationships": {}, "issues": []}
    if kind == "supplier":
        return _supplier(entity, raw)
    {"op_type": _op_type, "machine": _machine, "operator": _operator,
     "machine_group": _machine_group, "shift_profile": _shift_profile}[kind](entity, raw, state)
    if kind == "op_type" and raw["category"] == "internal" and availability is not None:
        entity["availability"] = dict(availability)
    entity["issues"].extend(dict(issue) for issue in availability_issues)
    if entity["status"] == "unknown":
        entity["fields"]["legacy_status"] = raw.get("status")
        message = "原停用状态的原因未登记，当前保留原值。" if raw.get("status") == "inactive" else "原资源状态无法识别，当前保留原值，未认定为启用或停用。"
        entity["issues"].append({"code": "legacy_status_unknown", "message": message})
    return entity


def _op_type(entity, raw, state):
    entity["fields"]["category"] = raw["category"]
    entity["fields"]["default_merge_mode"] = state["profile"]["default_merge_mode"] if state["profile"] else None
    entity["relationships"]["counts"] = state["dependencies"]


def _machine(entity, raw, state):
    entity["fields"]["category"] = raw["category"]
    if raw["status"] not in ("active", "maintain", "inactive"):
        entity["status"] = "unknown"
    relations = entity["relationships"]
    relations["counts"] = state["dependencies"]
    for name in ("op_type", "group"):
        related = _related(state[name])
        relations[name] = related
        relations[name + "_ref"] = related["ref"] if related else None
    if state["op_type"] and state["op_type"]["record"]["category"] != "internal":
        entity["issues"].append({"code": "machine_work_type_invalid", "message": "设备关联的工种不是自制工种，请重新选择；未认定其具备自制产能。"})


def _operator(entity, raw, state):
    entity["status"] = _operator_status(raw, state["profile"])
    relations = entity["relationships"]
    relations["counts"] = state["dependencies"]
    relations["skills"] = [_related(item) for item in state["skill_types"]]
    relations["skill_refs"] = [item["ref"] for item in relations["skills"]]
    relations["skills_declared"] = bool(state["skills"] or (state["profile"] and state["profile"]["skills_declared"]))
    relations["shift_profile"] = _related(state["shift"])
    relations["shift_profile_ref"] = relations["shift_profile"]["ref"] if relations["shift_profile"] else None
    relations["machine_authorization_count"] = len(state["machine_authorizations"])
    entity["issues"].extend(_authorization_issues(state["machine_authorizations"]))
    if any(item["record"]["category"] != "internal" for item in state["skill_types"]):
        entity["issues"].append({"code": "operator_skill_invalid", "message": "已登记技能含非自制工种，请核对；未认定其具备自制资格。"})
    if relations["skills_declared"] and not relations["skill_refs"]:
        entity["issues"].append({"code": "skills_empty", "message": "已明确登记为空技能集合，当前没有自制工种资格。"})
    if not state["machine_authorizations"]:
        entity["issues"].append({"code": "machine_authorization_missing", "message": "尚无设备操作授权；登记工种技能不会自动增加授权。"})


def _machine_group(entity, raw, state):
    if raw["status"] not in ("active", "inactive"):
        entity["status"] = "unknown"
    entity["relationships"]["machine_count"] = len(state["members"])


def _shift_profile(entity, raw, state):
    if raw["status"] not in ("active", "inactive"):
        entity["status"] = "unknown"
    entity["fields"].update({key: raw[key] for key in ("anchor_date", "cycle_days")})
    entity["fields"]["pattern"] = [{**{key: row[key] for key in ("day_offset", "shift_start", "shift_end")}, "is_rest": bool(row["is_rest"])} for row in state["pattern"]]
    entity["relationships"]["operator_count"] = len(state["members"])


def _supplier(entity, raw):
    state = supplier_state(raw["status"], raw["profile"])
    entity["status"] = "unknown" if state["inactive_reason"] == "unknown" else state["status"]
    entity["fields"]["default_days"] = raw["default_days"]
    refs = []
    for row in raw["op_types"]:
        if row["ref"] is None:
            raise WorkbenchCommandRejected("storage_failure", "供应商关联工种的永久引用缺失，请检查资料。", 500)
        refs.append({"ref": row["ref"], "business_code": row["op_type_id"], "label": row["name"],
                     "legacy": bool(row["legacy"]), "explicit": bool(row["explicit"])})
        if row["category"] != "external":
            entity["issues"].append({"code": "supplier_capability_invalid", "message": "供应商关联的工种不是外协工种，请重新选择；未认定其具备外协能力。"})
    entity["relationships"] = {"op_types": refs, "op_type_refs": [row["ref"] for row in refs],
                                "counts": {key: len(rows) for key, rows in raw["references"].items()}}
    if entity["status"] == "unknown":
        entity["fields"]["legacy_status"] = raw["status"]
        message = "原供应商停用原因未知，未认定为待复核。" if raw["status"] == "inactive" else "原供应商状态无法识别，当前保留原值，未认定为启用或停用。"
        entity["issues"].append({"code": "legacy_status_unknown", "message": message})
    return entity


def _authorization_issues(rows):
    """Expose affected link fields without changing raw authorization values."""
    issues = []
    labels = {"skill_level": "技能等级", "is_primary": "主操设备"}
    for row in rows:
        normalized = OperatorMachineQueryService._normalize_row(row)
        fields = normalized.get("dirty_fields", [])
        if fields:
            message = "设备“{}”的关联记录需核对，涉及字段：{}；当前仅按兼容规则解释，原值未改写。".format(
                row["machine_id"], "、".join(labels[field] for field in fields))
            issues.append({"code": "machine_authorization_dirty", "fields": list(fields), "message": message})
    return issues
