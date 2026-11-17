"""Validate raw template facts for an explicit batch operation refresh."""

from core.errors import ValidationError
from core.models.workbench_batch import number
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_source import SOURCE_MESSAGES, TemplateSourceFacts
from core.services.process.workflow_state import project_part_workflow

from .projection import issue


def template_diagnostics(rows, facts, resources):
    diagnostics = []
    sequences = set()
    types = resources.catalogs["op_type"]
    part_nos = {row["part_no"] for row in rows}
    referenced_groups = {row["ext_group_id"] for row in rows if row["ext_group_id"] is not None}
    part_groups = [
        row for row in facts["ExternalGroups"]
        if row["part_no"] in part_nos or row["group_id"] in referenced_groups
    ] if rows else []
    group_ids = {row["group_id"] for row in part_groups}
    source_rows = [
        row for row in facts["PartOperations"]
        if row["status"] == "active" and (row["part_no"] in part_nos or row["ext_group_id"] in group_ids)
    ] if group_ids else rows
    source_facts = TemplateSourceFacts(source_rows, part_groups, facts["Suppliers"],
                                      facts["WorkbenchSupplierOpTypes"], facts["WorkbenchSupplierProfiles"])
    for row in rows:
        if type(row["seq"]) is not int or row["seq"] <= 0:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 无效，请填写正整数。"))
        if row["seq"] in sequences:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 重复，请先整理工艺路线。"))
        sequences.add(row["seq"])
        kind = types.get(row["op_type_id"])
        group = source_facts.groups.get(row["ext_group_id"])
        errors = source_facts.issues(row, type_name=kind["name"] if kind else None,
                                     category=kind["category"] if kind else None)
        diagnostics.extend(issue("工序 " + str(row["seq"]) + " " + SOURCE_MESSAGES[code]) for code in errors)
        if row["source"] == "internal":
            diagnostics.extend(_internal_diagnostics(row))
        elif row["source"] == "external":
            diagnostics.extend(_external_diagnostics(row, group))
    return diagnostics


def template_status(facts, batch, resources, *, rows=None):
    """The detail and replacement preview apply the same completeness policy."""
    if rows is None:
        rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
    part = next((item for item in facts["Parts"] if item["part_no"] == batch["part_no"]), None)
    if part is None:
        raise WorkbenchCommandRejected("storage_failure", "这个批次对应的零件已经不在了。请刷新重试；仍不行请联系维护人员。", 500)
    workflow = project_part_workflow(part, bool(rows))
    diagnostics = template_diagnostics(rows, facts, resources)
    if not rows:
        diagnostics.insert(0, issue("尚未录入有效工序，请先完善工艺路线。"))
    elif workflow["origin"] == "managed" and not workflow["ready"]:
        stage = {"route": "工艺路线", "source": "工序归属", "hours": "工时定额"}[workflow["stage"]]
        diagnostics.append(issue("请先到工艺详情保存并确认" + stage + "。"))
    return {**workflow, "operation_count": len(rows), "complete": not diagnostics, "diagnostics": diagnostics}


def _missing(sequence, label):
    return [issue("工序 " + str(sequence) + " 的" + label + "未填写，请先补齐工艺。")]


def _number_diagnostic(value, sequence, label):
    if value is None:
        return _missing(sequence, label)
    try:
        number(value, label)
    except ValidationError:
        return [issue("工序 " + str(sequence) + " 的" + label + "必须为非负数。")]
    return []


def _internal_diagnostics(row):
    diagnostics = []
    for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
        diagnostics.extend(_number_diagnostic(row[key], row["seq"], label))
    return diagnostics


def _external_diagnostics(row, group):
    # 外协周期与整组周期的值域由表约束保证，只剩没填一种情况。
    merged = group and group["merge_mode"] == "merged"
    days = group["total_days"] if merged else row["ext_days"]
    return _missing(row["seq"], "整组外协周期" if merged else "外协周期") if days is None else []
