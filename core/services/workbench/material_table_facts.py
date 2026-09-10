"""Material cells reuse the same canonical cell and index logic as resources."""

from .resource_table_cells import number_cell, status_cell, text_cell
from .resource_table_index import ResourceTableIndex


def material_table_index(rows, project):
    records, cells, legacy_values = {}, {}, {}
    for row in rows:
        entity = project(row).entity
        code = entity["business_code"]
        records[code] = row
        legacy_values[code] = {"business_code": code, "label": row["name"], "status": row["status"], "stock_qty": row["stock_qty"]}
        cells[code] = {"business_code": text_cell(code), "label": text_cell(entity["label"]),
                       "spec": text_cell(row["spec"]), "stock_qty": number_cell(row["stock_qty"], row["unit"]),
                       "status": status_cell("material", row["status"])}
    return ResourceTableIndex(records, cells, legacy_values)
