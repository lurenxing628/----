"""Material cells reuse the same canonical cell and index logic as resources."""

import re

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.table_cells import number_cell, status_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex
from core.shared.strict_parse import is_exact_non_negative_number
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


def material_ref(row):
    if type(row.get("ref")) is not str or re.fullmatch(r"[0-9a-f]{48}", row["ref"]) is None or row.get("revision") is None:
        raise WorkbenchCommandRejected("storage_failure", "物料缺少系统编号，请联系维护人员核对资料。", 500)
    return row["ref"]


def material_stock(row):
    stock = row["stock_qty"]
    if stock is not None and not is_exact_non_negative_number(stock):
        cause = ValueError("Materials material_id={!r} stock_qty={!r}".format(row["material_id"], stock))
        raise WorkbenchCommandRejected(
            "storage_failure", "物料「{}」的库存数量不是 0 或大于 0 的有效数字，请核对原资料。".format(row["material_id"]),
            500) from cause
    return stock


def material_status(row):
    if row["status"] not in ("active", "inactive"):
        raise damaged_material_status(row["material_id"])
    return row["status"]


def material_counts(rows):
    statuses = [material_status(row) for row in rows]
    return {"total": len(rows), "active": statuses.count("active"), "inactive": statuses.count("inactive"),
            "stock_unknown": sum(row["stock_qty"] is None for row in rows)}


def material_table_index(rows):
    records, cells = {}, {}
    for row in rows:
        material_ref(row)
        status = material_status(row)
        stock = material_stock(row)
        code = row["material_id"]
        records[code] = row
        cells[code] = {"business_code": text_cell(code), "label": text_cell(row["name"]),
                       "spec": text_cell(row["spec"]), "stock_qty": number_cell(stock, row["unit"]),
                       "status": status_cell("material", status)}
    return ResourceTableIndex(records, cells)
