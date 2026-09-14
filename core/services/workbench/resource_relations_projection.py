"""Small read-only relation DTOs, with provenance distinct from eligibility."""

from .resource_metrics import _status

RELATION_KINDS = {"machines": "machine", "operators": "operator", "suppliers": "supplier"}
RELATION_BASIS = {
    "machines": {"code": "machine_op_type_binding", "message": "这个自制工种实际绑定的全部设备，含停机、停用和状态读不出来的；不代表现在就能排上。"},
    "operators": {"code": "recorded_skills_and_machine_authorizations", "message": "这个工种的技能记录，加上有对应设备授权的人；含停用的、没授权的和技能对不上的。旧授权不算技能登记，能对上也不代表现在就能排上。"},
    "suppliers": {"code": "legacy_and_explicit_capabilities", "message": "旧的单工种能力和单独设置的多工种能力合在一起，同一家只算一次；含停用和状态读不出来的，不代表现在就能接活。"},
}
_SOURCE_LABELS = {"op_type_binding": "设备实际工种绑定", "legacy": "旧单工种", "explicit": "单独设置的多工种", "mixed": "旧单工种和单独设置的多工种"}
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
        entity["issues"].append({"code": "legacy_status_unknown", "message": "这条资料的状态或停用原因看不懂，原值照样保留，系统不猜是启用还是停用。"})
    return entity


def relation_entity(identity, row, relation, parent_code, qualifications, authorizations):
    entity = _base_entity(RELATION_KINDS[relation], identity, row)
    if relation == "operators":
        _person_fields(entity, row, parent_code, qualifications[row["business_code"]], authorizations)
    else:
        source = "op_type_binding" if relation == "machines" else "mixed" if row["legacy"] and row["explicit"] else "legacy" if row["legacy"] else "explicit"
        entity["fields"].update({"relation_source": source, "relation_source_label": _SOURCE_LABELS[source]})
    if entity["status"] not in ("active", "unknown"):
        entity["issues"].append({"code": "resource_not_enabled", "message": "这个资源没有启用，关联关系照样保留，但不算当前可用。"})
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
    issues.append({"code": "qualification_scope", "message": "匹配授权数里含停机、停用和状态读不出来的设备。资格对上只说明技能门槛或旧授权规则通过，不代表人员启用、设备有授权、班表和占用都没问题。"})
    if qualification in ("explicit_empty", "explicit_mismatch"):
        issues.append({"code": "operator_skill_not_qualified", "message": "单独设置的技能里没有这个工种；留着的设备授权不能顶替技能。"})
    if skills is None:
        issues.append({"code": "legacy_authorization_fallback", "message": "还没单独登记技能，资格暂时按设备授权算；系统没有替你补技能记录。"})
    if not matching:
        issues.append({"code": "matching_machine_authorization_missing", "message": "这个人没有该工种设备的操作授权；登记技能不会自动加上设备授权。"})
    elif not enabled:
        issues.append({"code": "enabled_matching_machine_missing", "message": "有授权的匹配设备都没有启用，不算当前可用。"})
