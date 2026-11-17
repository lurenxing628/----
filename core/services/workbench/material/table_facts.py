"""Material cells reuse the same canonical cell and index logic as resources."""

from dataclasses import dataclass
from typing import Any, Dict

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.table_columns import index_columns
from core.services.workbench.facts.table_index import ResourceTableIndex
from core.shared.strict_parse import is_stored_number


@dataclass(frozen=True)
class MaterialRow:
    """A stored Materials row whose permanent ref and stock passed the storage check."""

    raw: Dict[str, Any]
    ref: str
    stock: Any


def material_row(raw):
    """The one storage-boundary check of a read Materials row. Every query LEFT JOINs the active identity for ref and
    revision; the identity table's CHECKs pin both, so only a missing identity fails."""
    ref = raw["ref"]
    if ref is None:
        raise WorkbenchCommandRejected("storage_failure", "物料缺少系统编号，请联系维护人员核对资料。", 500)
    stock = raw["stock_qty"]
    if stock is not None and not is_stored_number(stock):
        cause = ValueError("Materials material_id={!r} stock_qty={!r}".format(raw["material_id"], stock))
        raise WorkbenchCommandRejected(
            "storage_failure", "物料「{}」的库存数量不是有效数字或超出有效范围，请核对原资料。".format(raw["material_id"]),
            500) from cause
    return MaterialRow(raw, ref, stock)


def material_table_index(rows):
    """Index toolbar rows that already passed ``material_row``; each record is that ``MaterialRow``."""
    columns = index_columns("material")
    records, cells = {}, {}
    for row in rows:
        code = row.raw["material_id"]
        records[code] = row
        cells[code] = {column.name: column.cell(row) for column in columns}
    return ResourceTableIndex(records, cells)
