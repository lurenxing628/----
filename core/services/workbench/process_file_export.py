"""Complete process exports; selection never depends on the visible page."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import check_format, file_columns, file_error
from core.models.workbench_process_table_query import process_table_request, process_table_scope
from core.models.workbench_resource_action import resource_refs

from .process_file_values import export_value
from .resource_file_writer import XLSX_MAX_ROWS


def count_process_export_rows(kind, parts, facts, file_format):
    """Preflight the same cell encoding as download, without building a workbook."""
    columns = file_columns(kind)
    check_format(file_format)
    count = 0
    for count, row in enumerate(process_export_rows(kind, parts, facts), 1):
        if file_format == "xlsx" and count + 1 > XLSX_MAX_ROWS:
            raise file_error("XLSX 超过单表容量（含表头），未截断；可改用 CSV。", count + 1)
        for field in columns:
            if field in row and row[field] != "":
                export_value(row[field], field, count + 1, file_format)
    return count


def select_export_parts(reader, *, selection, scope, refs=None, target_ref=None):
    if selection not in ("all", "filtered", "explicit") or (refs is not None) != (selection == "explicit"):
        raise WorkbenchCommandRejected("invalid_input", "请选择全部、全部筛选结果或明确选中项；只有选中项接受引用。", 400)
    if target_ref is not None and (selection != "explicit" or refs != [target_ref] or scope):
        raise WorkbenchCommandRejected("invalid_input", "详情只能导出当前零件，不能切换为其他范围。", 400)
    normalized = process_table_scope(scope)
    parts = {row["ref"]: row for row in reader.facts()["parts"]}
    if selection == "explicit":
        selected = resource_refs(refs, allow_empty=True)
        for ref in selected:
            reader.resolve(ref)
            if ref not in parts:
                raise WorkbenchCommandRejected("storage_failure", "零件引用与实际资料不一致，未忽略该记录。", 500)
    else:
        normalized = process_table_scope({}) if selection == "all" else normalized
        selected = [row["ref"] for row in reader.table().matching_rows(process_table_request(normalized))]
    return [parts[ref] for ref in selected], {} if target_ref is not None else normalized


def process_export_rows(kind, parts, facts):
    file_columns(kind)
    if kind == "route":
        for part in parts:
            yield {"business_code": part["part_no"], "label": part["part_name"],
                   "route_raw": part["route_raw"], "remark": part["remark"]}
        return
    grouped = {}
    for row in facts["operations"]:
        if row["status"] == "active":
            grouped.setdefault(row["part_no"], []).append(row)
    groups = {row["group_id"]: row for row in facts["groups"]}
    for part in parts:
        for row in grouped.get(part["part_no"], []):
            yield _hours_export_row(part["part_no"], row, groups)


def _hours_export_row(part_no, row, groups):
    group = groups.get(row["ext_group_id"])
    if row["ext_group_id"] is not None and (group is None or group["part_no"] != part_no):
        raise WorkbenchCommandRejected("constraint_conflict", "工序关联的外协组缺失或属于其他零件，未忽略原关联。")
    internal = row["source"] == "internal"
    return {"business_code": part_no, "sequence": row["seq"], "op_type_name": row["op_type_name"],
            "source": row["source"], "setup_hours": row["setup_hours"] if internal else None,
            "unit_hours": row["unit_hours"] if internal else None,
            "external_days": row["ext_days"] if row["source"] == "external" else None,
            "group_start": group["start_seq"] if group else None, "group_end": group["end_seq"] if group else None,
            "group_total_days": group["total_days"] if group and group["merge_mode"] == "merged" else None}
