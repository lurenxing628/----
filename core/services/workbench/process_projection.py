"""Truthful legacy template projection, with no inferred human confirmations."""

import math
import re

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import _group_facts


def capabilities():
    return {"route_preview": True, "create": True, "delete": True, "stage_confirm": True, "import": True, "export": True}


def require_ref(value, label):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("storage_failure", label + "永久引用缺失，未自动修补数据；请检查数据库。", 500)
    return value


def issue(code, message):
    return {"code": code, "message": message}


def public_sequence(value):
    # Keep full SQLite integers readable without JavaScript rounding their displayed sequence.
    return value if type(value) is int and abs(value) <= (1 << 53) - 1 else str(value)


def legacy_workflow(has_operations):
    return {"origin": "legacy", "stage": "source" if has_operations else "route", "ready": False,
            "route": {"state": "present" if has_operations else "missing", "confirmed_at": None, "confirmed_by": None},
            "source": {"state": "unconfirmed" if has_operations else "locked", "confirmed_at": None, "confirmed_by": None},
            "hours": {"state": "locked", "confirmed_at": None, "confirmed_by": None}}


def project_part(row, operations, workflow=None):
    active = [op for op in operations if op["status"] == "active"]
    internal = sum(op["source"] == "internal" for op in active)
    external = sum(op["source"] == "external" for op in active)
    workflow = legacy_workflow(bool(active)) if workflow is None else workflow
    issues = [issue("legacy_confirmation_unknown", "存量模板未记录逐序人工确认，未将已有归属或工时当作已确认。")] if workflow["origin"] == "legacy" else []
    if workflow["origin"] == "managed" and not workflow["ready"]:
        issues.append(issue("workflow_pending", "工艺尚未完成确认，暂不能用它生成新的批次工序。"))
    if row["route_parsed"] not in ("yes", "no"):
        issues.append(issue("route_parsed_unknown", "原有路线解析标记不明确，当前保留原值。"))
    if row["route_parsed"] == "yes" and not active:
        issues.append(issue("template_missing", "原标记为已解析，但没有有效模板工序。"))
    if active and row["route_parsed"] != "yes":
        issues.append(issue("template_route_state_mismatch", "已有模板工序与路线解析标记不一致，请核对。"))
    return {"ref": require_ref(row["ref"], "零件"), "business_code": row["part_no"], "label": row["part_name"], "status": None,
            "fields": {name: row[name] for name in ("route_raw", "route_parsed", "remark")},
            "relationships": {"batch_count": row["batch_count"], "operation_count": len(active),
                              "internal_count": internal, "external_count": external,
                              "unclassified_count": len(active) - internal - external},
            "workflow": workflow, "issues": issues, "write_context": None}


def _number(value, label, issues, *, positive=False):
    if value is None:
        issues.append(issue("value_missing", label + "未填写。"))
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        issues.append(issue("value_invalid", label + "原值不合法，未用默认值替代。"))
        return None
    return value


def _relation(row, name, exists, ref, label, issues):
    if row[name] is None or row[name] == "":
        return None
    if row[exists] is None:
        issues.append(issue("relation_missing", label + "记录已不存在，未猜测绑定其他对象。"))
        return None
    return require_ref(row[ref], label)


def _setup_and_unit_hours(row, source, issues):
    setup = _number(row["setup_hours"], "换型工时", issues) if source == "internal" or row["setup_hours"] is not None else None
    unit = _number(row["unit_hours"], "单件工时", issues) if source == "internal" or row["unit_hours"] is not None else None
    return setup, unit


def _external_days(row, source, group_ref, group, issues):
    if group is not None and group["issues"]:
        issues.append(issue("external_group_invalid", "关联外协组规则不合法，请核对组范围、成员和周期；未用组周期替代本序原值。"))
    group_cycle = (source == "external" and row["status"] == "active" and group_ref is not None
                   and group is not None and group["ref"] == group_ref and group["merge_mode"] == "merged"
                   and group["total_days"] is not None and not group["issues"])
    # Only an absent member value delegates to the group; non-NULL values still need validation.
    if row["ext_days"] is None and group_cycle:
        return None, "group"
    days = _number(row["ext_days"], "外协周期", issues, positive=source == "external") if source == "external" or row["ext_days"] is not None else None
    return days, "operation" if days is not None else None


def project_operation(row, confirmation, group=None):
    issues = []
    if type(row["seq"]) is not int or row["seq"] <= 0:
        issues.append(issue("sequence_invalid", "原工序号不合法，当前按原值展示；未自动改号。"))
    source = row["source"] if row["source"] in ("internal", "external") else None
    if source is None:
        issues.append(issue("source_unknown", "原工序归属不明确。"))
    op_ref = _relation(row, "op_type_id", "op_type_exists", "op_type_ref", "工种", issues)
    if not op_ref:
        issues.append(issue("op_type_unbound", "尚未绑定有效工种，归属仍需核对。"))
    supplier_ref = _relation(row, "supplier_id", "supplier_exists", "supplier_ref", "供应商", issues)
    group_ref = _relation(row, "ext_group_id", "group_exists", "external_group_ref", "外协组", issues)
    if group_ref and row["group_part_no"] != row["part_no"]:
        issues.append(issue("external_group_part_mismatch", "关联外协组属于其他零件，未将它作为本模板规则。"))
        group_ref = None
    if op_ref and row["op_type_category"] != source:
        issues.append(issue("source_category_mismatch", "当前工种类别与本序原归属不一致，请核对；未修改任何一方。"))
    setup, unit = _setup_and_unit_hours(row, source, issues)
    days, days_source = _external_days(row, source, group_ref, group, issues)
    if source == "internal" and unit == 0 and confirmation["hours"]["state"] != "confirmed":
        issues.append(issue("zero_unit_hours_review", "单件工时为0，请复核；未当作空值或自动修改。"))
    if row["status"] not in ("active", "deleted"):
        issues.append(issue("operation_status_unknown", "原工序状态不明确，未计为有效模板工序。"))
    return {"ref": require_ref(row["ref"], "模板工序"), "sequence": public_sequence(row["seq"]), "label": row["op_type_name"],
            "source": source, "op_type_ref": op_ref, "op_type_label": row["op_type_label"],
            "supplier_ref": supplier_ref, "supplier_label": row["supplier_label"], "external_group_ref": group_ref,
            "setup_hours": setup, "unit_hours": unit, "external_days": days, "external_days_source": days_source,
            "status": row["status"], "issues": issues,
            "confirmation": confirmation}


def _group_member_issues(row, members, issues):
    # Reuse the confirmation rule; also retain the command-side cross-part reference guard.
    facts = dict(row, members=[[op["ref"], op["seq"], op["source"]] for op in members])
    _, valid = _group_facts(facts, row["part_no"])
    if any(op["part_no"] != row["part_no"] for op in members):
        issues.append(issue("external_group_part_mismatch", "外协组被其他零件的有效工序引用，未将它作为有效合并周期。"))
    if not valid and not any(item["code"] in ("external_group_range_invalid", "external_group_mode_unknown") for item in issues):
        issues.append(issue("external_group_members_invalid", "外协组含非外协或超出组范围的有效成员，未将它作为有效合并周期。"))


def project_group(row, members=None):
    issues = []
    supplier = _relation(row, "supplier_id", "supplier_exists", "supplier_ref", "供应商", issues)
    if type(row["start_seq"]) is not int or type(row["end_seq"]) is not int or not 0 < row["start_seq"] <= row["end_seq"]:
        issues.append(issue("external_group_range_invalid", "外协组序号范围不合法，未自动交换或修正。"))
    if row["merge_mode"] not in ("separate", "merged"):
        issues.append(issue("external_group_mode_unknown", "原外协组周期策略不明确。"))
    if members is not None:
        _group_member_issues(row, members, issues)
    days = _number(row["total_days"], "合并周期", issues, positive=True) if row["merge_mode"] == "merged" or row["total_days"] is not None else None
    return {"ref": require_ref(row["ref"], "模板外协组"), "start_sequence": public_sequence(row["start_seq"]), "end_sequence": public_sequence(row["end_seq"]),
            "merge_mode": row["merge_mode"], "total_days": days, "supplier_ref": supplier,
            "supplier_label": row["supplier_label"], "remark": row["remark"], "issues": issues}
