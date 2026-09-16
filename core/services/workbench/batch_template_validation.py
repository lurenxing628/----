"""Validate raw template facts for an explicit batch operation refresh."""

from core.errors import ValidationError
from core.models.workbench_batch import number
from core.services.workbench.batch_projection import issue


def template_diagnostics(rows, facts, batch):
    diagnostics = []
    sequences = set()
    types = {row["op_type_id"] for row in facts["OpTypes"]}
    for row in rows:
        if type(row["seq"]) is not int or row["seq"] <= 0:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 无效，请填写正整数。"))
        if row["seq"] in sequences:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 重复，请先整理工艺路线。"))
        sequences.add(row["seq"])
        if row["source"] not in ("internal", "external"):
            diagnostics.append(issue("工序 " + str(row["seq"]) + " 尚未明确自制或外协归属。"))
        if row["op_type_id"] not in types:
            diagnostics.append(issue("工序 " + str(row["seq"]) + " 缺少明确工种。"))
        if row["source"] == "internal":
            diagnostics.extend(_internal_diagnostics(row))
        elif row["source"] == "external":
            diagnostics.extend(_external_diagnostics(row, facts, batch))
    return diagnostics


def template_status(facts, batch):
    """The detail and replacement preview apply the same completeness policy."""
    rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
    workflow = facts["workflow"][batch["part_no"]]["workflow"]
    diagnostics = template_diagnostics(rows, facts, batch)
    if not rows:
        diagnostics.insert(0, issue("尚未录入有效工序，请先完善工艺路线。"))
    elif workflow["origin"] == "managed" and not workflow["ready"]:
        stage = {"route": "工艺路线", "source": "工序归属", "hours": "工时定额"}[workflow["stage"]]
        diagnostics.append(issue("请先到工艺详情保存并确认" + stage + "。"))
    return {**workflow, "operation_count": len(rows), "complete": not diagnostics, "diagnostics": diagnostics}


def _number_diagnostic(value, sequence, label, *, positive=False):
    prefix = "工序 " + str(sequence) + " 的" + label
    if value is None:
        return [issue(prefix + "未填写，请先补齐工艺。")]
    try:
        number(value, label, positive=positive)
    except ValidationError:
        return [issue(prefix + ("必须大于 0。" if positive else "必须为非负数。"))]
    return []


def _internal_diagnostics(row):
    diagnostics = []
    for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
        diagnostics.extend(_number_diagnostic(row[key], row["seq"], label))
    return diagnostics


def _external_diagnostics(row, facts, batch):
    diagnostics = []
    group = next((g for g in facts["ExternalGroups"] if g["group_id"] == row["ext_group_id"]), None)
    days = group["total_days"] if group and group["merge_mode"] == "merged" else row["ext_days"]
    if row["ext_group_id"] is not None and (not group or group["part_no"] != batch["part_no"]
                                          or group["merge_mode"] not in ("merged", "separate")):
        diagnostics.append(issue("工序 " + str(row["seq"]) + " 的外协组关系不完整，请先完善工艺。"))
    diagnostics.extend(_number_diagnostic(days, row["seq"], "整组外协周期" if group and group["merge_mode"] == "merged" else "外协周期", positive=True))
    if row["supplier_id"] is None:
        diagnostics.append(issue("工序 " + str(row["seq"]) + " 的供应商未填写。"))
    elif not any(supplier["supplier_id"] == row["supplier_id"] and supplier["status"] == "active" for supplier in facts["Suppliers"]):
        diagnostics.append(issue("工序 " + str(row["seq"]) + " 的供应商不存在或已停用。"))
    return diagnostics
