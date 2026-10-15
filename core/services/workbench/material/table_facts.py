"""Material cells reuse the same canonical cell and index logic as resources."""

from core.services.workbench.facts.table_cells import number_cell, status_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex

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


def _sqlite_order(value):
    if value is None:
        return (0, "")
    if isinstance(value, (int, float)):
        return (1, value)
    if isinstance(value, str):
        return (2, value)
    return (3, value)


def material_ordered_rows(rows, query):
    """Captured raw rows are already business-code ASC; stable sorting keeps that tie order."""
    if query.sort == "business_code" and query.direction == "asc":
        return rows
    return sorted(rows, key=lambda row: _sqlite_order(row[_SORT_FIELDS[query.sort]]),
                  reverse=query.direction == "desc")


def material_counts(rows):
    return {"total": len(rows), "active": sum(row["status"] == "active" for row in rows),
            "inactive": sum(row["status"] == "inactive" for row in rows),
            "unknown": sum(row["status"] not in ("active", "inactive") for row in rows),
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
