"""Material cells reuse the same canonical cell and index logic as resources."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.table_cells import number_cell, status_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex
from data.repositories.sqlite_rows import sql_order

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_BYTE_LOWER = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")
_SORT_FIELDS = {"business_code": "material_id", "label": "name", "spec": "spec", "stock_qty": "stock_qty", "status": "status"}


def material_toolbar_rows(rows, query):
    """Match the existing SQLite toolbar: ASCII lower, NULL exclusion, exact status."""
    needle = query.query.translate(_ASCII_LOWER)
    byte_needle = needle.encode("utf-8")

    def matches(value):
        if value is None:
            return False
        if isinstance(value, bytes):
            return byte_needle in value.translate(_BYTE_LOWER)
        return needle in value.translate(_ASCII_LOWER)

    return [row for row in rows
            if (query.status is None or row["status"] == query.status)
            and (not needle or any(matches(row[field]) for field in ("material_id", "name", "spec")))]


def material_ordered_rows(rows, query):
    """Captured raw rows are already business-code ASC; stable sorting keeps that tie order."""
    if query.sort == "business_code" and query.direction == "asc":
        return rows
    return sorted(rows, key=lambda row: sql_order(row[_SORT_FIELDS[query.sort]]),
                  reverse=query.direction == "desc")


def damaged_material_status(code):
    # 写入口只产出启用或停用；其余值只可能是存储被改坏，直接拒绝，不猜是启用还是停用。
    return WorkbenchCommandRejected("storage_failure", f"物料「{code}」的状态存得不对，系统没有猜是启用还是停用。"
                                    "请联系维护人员核对资料。", 500)


def material_status(row):
    if row["status"] not in ("active", "inactive"):
        raise damaged_material_status(row["material_id"])
    return row["status"]


def material_counts(rows):
    statuses = [material_status(row) for row in rows]
    return {"total": len(rows), "active": statuses.count("active"), "inactive": statuses.count("inactive"),
            "stock_unknown": sum(row["stock_qty"] is None for row in rows)}


def material_table_index(rows, project):
    records, cells, legacy_values = {}, {}, {}
    for row in rows:
        record = project(row)
        entity = record.entity
        code = entity["business_code"]
        records[code] = record
        legacy_values[code] = {"business_code": code, "label": row["name"], "status": row["status"], "stock_qty": row["stock_qty"]}
        cells[code] = {"business_code": text_cell(code), "label": text_cell(entity["label"]),
                       "spec": text_cell(row["spec"]), "stock_qty": number_cell(row["stock_qty"], row["unit"]),
                       "status": status_cell("material", row["status"])}
    return ResourceTableIndex(records, cells, legacy_values)
