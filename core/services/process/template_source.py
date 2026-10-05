"""Source validity shared by template confirmation and batch replacement."""

from core.models.resource_capabilities import supports_source


def valid_supplier(fact):
    return bool(fact is not None and fact["status"] == "active"
                and fact["capable"] and fact["inactive_reason"] is None)


def valid_external_group(group, part_no, members):
    valid_range = (type(group["start_seq"]) is int and type(group["end_seq"]) is int
                   and 0 < group["start_seq"] <= group["end_seq"])
    return (group["part_no"] == part_no and group["merge_mode"] in ("separate", "merged") and valid_range
            and all(source == "external" and type(seq) is int and group["start_seq"] <= seq <= group["end_seq"]
                    for seq, source in members))


def _source_type_issues(source, type_name, category):
    """来源和工种是每种归属共用的前置事实，按原顺序给出诊断。"""
    issues = []
    if source not in ("internal", "external"):
        issues.append("source_missing")
    if type_name is None:
        issues.append("type_missing")
    elif source in ("internal", "external") and not supports_source(category, source):
        issues.append("type_source_mismatch")
    return issues


def _external_group_issue(op, group, group_valid):
    if not group_valid or op["ext_group_id"] is not None and group is None:
        return "group_invalid"
    if group is not None and group["supplier_id"] is not None and group["supplier_id"] != op["supplier_id"]:
        return "group_supplier_mismatch"
    return None


def _external_source_issues(op, supplier_valid, group, group_valid):
    issues = []
    if op["supplier_id"] is None:
        issues.append("supplier_missing")
    elif not supplier_valid:
        issues.append("supplier_invalid")
    group_issue = _external_group_issue(op, group, group_valid)
    if group_issue is not None:
        issues.append(group_issue)
    return issues


def source_issues(op, *, type_name, category, supplier_valid, group, group_valid):
    """Return fact errors; callers decide whether to display or reject them."""
    source = op["source"]
    issues = _source_type_issues(source, type_name, category)
    if source == "external":
        issues.extend(_external_source_issues(op, supplier_valid, group, group_valid))
    elif source == "internal" and (op.get("supplier_id") is not None or op.get("ext_group_id") is not None):
        issues.append("internal_external_binding")
    return issues
