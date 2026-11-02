"""Complete process exports; selection never depends on the visible page."""

from core.models.process_route_text import serialize_route_rows
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import file_columns, file_error
from core.services.workbench.facts.file_writer import XLSX_MAX_ROWS

from .file_values import export_value


def count_process_export_rows(kind, parts, facts, file_format):
    """Preflight the same cell encoding as download, without building a workbook."""
    columns = file_columns(kind)
    count = 0
    for count, row in enumerate(process_export_rows(kind, parts, facts), 1):
        if file_format == "xlsx" and count + 1 > XLSX_MAX_ROWS:
            raise file_error("行数超过 XLSX 单表上限（算上表头）。请改用 CSV 导出。", count + 1)
        for field in columns:
            if field in row and row[field] != "":
                export_value(row[field], field, count + 1, file_format)
    return count


def _requires_workflow_table(query):
    return (
        query.stage is not None
        or "stage" in query.column_filters
        or any(item["field"] == "stage" for item in query.ordering())
    )


def select_export_parts(reader, refs, request):
    """The export's current parts: explicit refs in their order, else request's matching rows; both were admitted at preflight."""
    parts = {row["ref"]: row for row in reader.raw_facts()["parts"]}
    if refs is None:
        table = reader.table() if _requires_workflow_table(request) else reader.raw_table()
        refs = [row["ref"] for row in table.matching_rows(request)]
    elif reader.repo.part_ref is None:
        for ref in refs:
            if ref not in parts:
                raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了。请刷新列表后重新选择。", 404)
    else:
        for ref in refs:
            reader.identity_of(ref)
            if ref not in parts:
                raise WorkbenchCommandRejected("storage_failure", "零件编号和实际资料对不上。请刷新列表后重新选择。", 500)
    return [parts[ref] for ref in refs]


def _seq_key(row):
    """存量工序号可能混入非整数；先排整数，坏值随后由逐格校验报出结构化的文件错误。"""
    return (0, row["seq"]) if type(row["seq"]) is int else (1, repr(row["seq"]))


def process_export_rows(kind, parts, facts):
    grouped = {}
    for row in facts["operations"]:
        if row["status"] == "active":
            grouped.setdefault(row["part_no"], []).append(row)
    if kind == "route":
        for index, part in enumerate(parts, 2):
            operations = sorted(grouped.get(part["part_no"], []), key=_seq_key)
            # 路线文本由工序号和工种拼成，与工时导出同一逐格规则校验存量值，坏值报出所在行。
            for row in operations:
                export_value(row["seq"], "sequence", index, "csv")
                export_value(row["op_type_name"], "op_type_name", index, "csv")
            raw = serialize_route_rows([(row["seq"], row["op_type_name"]) for row in operations]) if operations else part["route_raw"]
            yield {"business_code": part["part_no"], "label": part["part_name"],
                   "route_raw": raw, "remark": part["remark"]}
        return
    groups = {row["group_id"]: row for row in facts["groups"]}
    for part in parts:
        written_groups = set()
        for row in sorted(grouped.get(part["part_no"], []), key=_seq_key):
            exported = _hours_export_row(part["part_no"], row, groups)
            if row["ext_group_id"] in written_groups:
                exported.pop("group_total_days", None)
            elif exported.get("group_total_days") is not None:
                written_groups.add(row["ext_group_id"])
            # Missing values are incomplete work, not requests to clear them on re-import.
            yield {key: value for key, value in exported.items() if value is not None}


def _hours_export_row(part_no, row, groups):
    group = groups.get(row["ext_group_id"])
    if row["ext_group_id"] is not None and (group is None or group["part_no"] != part_no):
        raise WorkbenchCommandRejected("constraint_conflict", "工序关联的外协组找不到，或者属于别的零件。请到基础资料核对外协组。")
    internal = row["source"] == "internal"
    merged = group is not None and group["merge_mode"] == "merged"
    # 合并外协组按整段周期排产，成员保留的逐序旧周期不生效（可能是未清理的旧值），不导出。
    return {"business_code": part_no, "sequence": row["seq"], "op_type_name": row["op_type_name"],
            "source": row["source"], "setup_hours": row["setup_hours"] if internal else None,
            "unit_hours": row["unit_hours"] if internal else None,
            "external_days": row["ext_days"] if row["source"] == "external" and not merged else None,
            "group_start": group["start_seq"] if group else None, "group_end": group["end_seq"] if group else None,
            "group_total_days": group["total_days"] if merged else None}
