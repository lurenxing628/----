"""Batch-scoped material edits; row keys require the matching write snapshot."""

import hashlib

from core.errors import ValidationError

from .workbench_batch import number, object_fields, public_ref
from .workbench_preflight import local_date


def normalize_arrivals(value):
    if type(value) is not list or len(value) > 200:
        raise ValidationError("每条需求最多登记 200 次到料。", field="arrivals")
    rows = []
    for row in value:
        object_fields(row, ("arrival_date", "quantity"), ("arrival_date", "quantity"))
        rows.append({"arrival_date": local_date(row["arrival_date"]).isoformat(),
                     "quantity": number(row["quantity"], "quantity", positive=True)})
    return sorted(rows, key=lambda row: (row["arrival_date"], row["quantity"]))


def material_row_key(batch_ref, row):
    value = "{}:{}:{}".format(batch_ref, row["id"], row["material_id"])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _key(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValidationError("物料需求已变化，请刷新批次后重新核对。", field="row_key")
    return value


def normalize_material_changes(payload):
    object_fields(payload, ("rows", "removed_keys"), ("rows", "removed_keys"))
    rows, removed = payload["rows"], payload["removed_keys"]
    if type(rows) is not list or type(removed) is not list or len(rows) + len(removed) > 2000:
        raise ValidationError("一次最多维护 2000 条物料需求。", field="rows")
    result = []
    for row in rows:
        object_fields(row, ("row_key", "material_ref", "required_quantity", "available_quantity", "operation_ref", "arrivals"),
                      ("row_key", "material_ref", "required_quantity", "available_quantity"))
        item = {"row_key": _key(row["row_key"]) if row["row_key"] is not None else None,
            "material_ref": public_ref(row["material_ref"]),
            "required_quantity": number(row["required_quantity"], "required_quantity", positive=True),
            "available_quantity": number(row["available_quantity"], "available_quantity")}
        if "operation_ref" in row:
            item["operation_ref"] = public_ref(row["operation_ref"]) if row["operation_ref"] is not None else None
        if "arrivals" in row:
            item["arrivals"] = normalize_arrivals(row["arrivals"])
        result.append(item)
    keys = [row["row_key"] for row in result if row["row_key"] is not None] + [_key(key) for key in removed]
    if len(keys) != len(set(keys)):
        raise ValidationError("同一条物料需求不能重复修改或同时移除。", field="rows")
    return {"rows": result, "removed_keys": list(removed)}
