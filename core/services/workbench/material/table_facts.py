"""Material cells reuse the same canonical cell and index logic as resources."""

import re
from dataclasses import dataclass
from typing import Any, Dict

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


@dataclass(frozen=True)
class MaterialRow:
    """A stored Materials row whose permanent ref and stock passed the storage check."""

    raw: Dict[str, Any]
    ref: str
    stock: Any
    status: str


def material_row(raw):
    """The one storage-boundary check of a read Materials row (every query selects ref and revision)."""
    ref = raw["ref"]
    if type(ref) is not str or re.fullmatch(r"[0-9a-f]{48}", ref) is None or raw["revision"] is None:
        raise WorkbenchCommandRejected("storage_failure", "物料缺少系统编号，请联系维护人员核对资料。", 500)
    stock = raw["stock_qty"]
    if stock is not None and not is_exact_non_negative_number(stock):
        cause = ValueError("Materials material_id={!r} stock_qty={!r}".format(raw["material_id"], stock))
        raise WorkbenchCommandRejected(
            "storage_failure", "物料「{}」的库存数量不是 0 或大于 0 的有效数字，请核对原资料。".format(raw["material_id"]),
            500) from cause
    return MaterialRow(raw, ref, stock, material_status(raw))


def material_status(row):
    return "inactive" if row["status"] == "inactive" else "active"


def material_counts(rows):
    statuses = [material_status(row) for row in rows]
    return {"total": len(rows), "active": statuses.count("active"), "inactive": statuses.count("inactive"),
            "stock_unknown": sum(row["stock_qty"] is None for row in rows)}


def material_table_index(rows):
    """Index toolbar rows that already passed ``material_row``; each record is that ``MaterialRow``."""
    records, cells = {}, {}
    for row in rows:
        raw = row.raw
        code = raw["material_id"]
        records[code] = row
        cells[code] = {"business_code": text_cell(code), "label": text_cell(raw["name"]),
                       "spec": text_cell(raw["spec"]), "stock_qty": number_cell(row.stock, raw["unit"]),
                       "status": status_cell("material", row.status)}
    return ResourceTableIndex(records, cells)
