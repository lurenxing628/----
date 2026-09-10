"""Small read-only relation DTOs, with provenance distinct from eligibility."""

from .resource_metrics import _status

RELATION_KINDS = {"machines": "machine", "operators": "operator", "suppliers": "supplier"}
RELATION_BASIS = {
    "machines": {"code": "machine_op_type_binding", "message": "实际绑定此自制工种的全部设备，含检修、停用及未知状态；不代表当前可排。"},
    "operators": {"code": "recorded_skills_and_machine_authorizations", "message": "此工种的技能记录与其设备授权人员的并集，含停用、缺授权及显式技能不匹配人员；旧授权不等于技能登记，资格匹配不代表当前可排。"},
    "suppliers": {"code": "legacy_and_explicit_capabilities", "message": "旧单工种与显式多工种能力的去重并集，含停用及未知状态；不代表当前可承接。"},
}
_SOURCE_LABELS = {"op_type_binding": "设备实际工种绑定", "legacy": "旧单工种", "explicit": "显式多工种", "mixed": "旧单工种及显式多工种"}
_PERSON_SOURCES = {"skill": "工种技能记录", "machine_authorization": "匹配设备的操作授权", "mixed": "工种技能记录及匹配设备授权"}


def _base_entity(kind, identity, row):
    profile = {"inactive_reason": row.get("inactive_reason")}
    status = _status(kind, row, profile)
    entity = {"kind": kind, "ref": identity.ref, "business_code": identity.entity_key,
              "label": row["name"], "status": status, "fields": {"remark": row["remark"]},
              "issues": [], "write_context": None}
    if kind == "machine":
        entity["fields"]["category"] = row["category"]
    if kind == "supplier":
        entity["fields"]["default_days"] = row["default_days"]
    if status == "unknown":
        entity["fields"]["legacy_status"] = row["status"]
        entity["issues"].append({"code": "legacy_status_unknown", "message": "原状态或停用原因无法识别，保留原值，未推断启用或停用原因。"})
    return entity


def relation_entity(identity, row, relation, parent_code, qualifications, authorizations):
    entity = _base_entity(RELATION_KINDS[relation], identity, row)
    if relation == "operators":
        _person_fields(entity, row, parent_code, qualifications[row["business_code"]], authorizations)
    else:
        source = "op_type_binding" if relation == "machines" else "mixed" if row["legacy"] and row["explicit"] else "legacy" if row["legacy"] else "explicit"
        entity["fields"].update({"relation_source": source, "relation_source_label": _SOURCE_LABELS[source]})
    if entity["status"] not in ("active", "unknown"):
        entity["issues"].append({"code": "resource_not_enabled", "message": "此资源未启用，仍保留真实关联；未认定为当前可用。"})
    return entity


def _person_fields(entity, row, parent_code, skills, authorizations):
    matching = [item for item in authorizations if item["op_type_id"] == parent_code]
    registered = row["skill_type"] is not None
    source = "mixed" if registered and matching else "skill" if registered else "machine_authorization"
    qualification = "legacy_fallback" if skills is None else "explicit_match" if parent_code in skills else "explicit_empty" if not skills else "explicit_mismatch"
    enabled = sum(item["machine_status"] == "active" for item in matching)
    fields = entity["fields"]
    fields.update({"relation_source": source, "relation_source_label": _PERSON_SOURCES[source],
                   "skill_registered": registered, "skills_declared": skills is not None,
                   "explicit_declaration": row["skills_declared"] == 1,
                   "skill_level": row["skill_level"], "skill_is_primary": row["skill_is_primary"],
                   "machine_authorization_count": len(authorizations),
                   "matching_machine_authorization_count": len(matching),
                   "enabled_matching_machine_authorization_count": enabled,
                   "qualification_basis": qualification,
                   "qualification_matches": skills is None or parent_code in skills})
    issues = entity["issues"]
    issues.append({"code": "qualification_scope", "message": "匹配授权数包含检修、停用及未知状态的设备；资格匹配只解释技能门槛或旧授权规则，不代表人员启用、设备授权、日历和占用等排程条件均已满足。"})
    if qualification in ("explicit_empty", "explicit_mismatch"):
        issues.append({"code": "operator_skill_not_qualified", "message": "显式技能不包含此工种；保留的设备授权不会绕过技能限制。"})
    if skills is None:
        issues.append({"code": "legacy_authorization_fallback", "message": "尚未登记显式技能，现有资格规则沿用设备授权；未生成技能记录。"})
    if not matching:
        issues.append({"code": "matching_machine_authorization_missing", "message": "没有此工种设备的操作授权；技能记录不会自动增加设备授权。"})
    elif not enabled:
        issues.append({"code": "enabled_matching_machine_missing", "message": "已授权的匹配设备均未启用；未认定为当前可用。"})
