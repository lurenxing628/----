"""Validate raw template facts for an explicit batch operation refresh."""

from core.models.workbench_batch import number
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_projection import issue


def template_diagnostics(rows, facts, batch):
    diagnostics = []
    for row in rows:
        if type(row["seq"]) is not int or row["seq"] <= 0:
            raise WorkbenchCommandRejected("constraint_conflict", "模板工序号不合法，不能自动改号。")
        if row["source"] not in ("internal", "external"):
            raise WorkbenchCommandRejected("constraint_conflict", "模板工序归属不明确，不能让旧运行时将其默认成自制。")
        if row["op_type_id"] is None:
            diagnostics.append(issue("工序 " + str(row["seq"]) + " 缺少明确工种。"))
        if row["source"] == "internal":
            diagnostics.extend(_internal_diagnostics(row))
        else:
            diagnostics.extend(_external_diagnostics(row, facts, batch))
    return diagnostics


def _internal_diagnostics(row):
    diagnostics = []
    for key in ("setup_hours", "unit_hours"):
        number(row[key], key, nullable=True)
        if row[key] is None:
            diagnostics.append(issue("工序 " + str(row["seq"]) + " 的工时待补齐，保留原值。"))
    return diagnostics


def _external_diagnostics(row, facts, batch):
    diagnostics = []
    group = next((g for g in facts["ExternalGroups"] if g["group_id"] == row["ext_group_id"]), None)
    days = group["total_days"] if group and group["merge_mode"] == "merged" else row["ext_days"]
    if row["ext_group_id"] is not None and (not group or group["part_no"] != batch["part_no"]
                                          or group["merge_mode"] not in ("merged", "separate")):
        raise WorkbenchCommandRejected("constraint_conflict", "模板外协组关系不完整，不能按单工序周期猜测。")
    number(days, "external_days", positive=True, nullable=True)
    if days is None:
        diagnostics.append(issue("工序 " + str(row["seq"]) + " 的外协周期待补齐。"))
    if row["supplier_id"] is None:
        diagnostics.append(issue("工序 " + str(row["seq"]) + " 的供应商未填写。"))
    return diagnostics
