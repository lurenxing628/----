"""A work type can support two sources; each operation still chooses one."""

from typing import Any

from .enums import OpTypeCategory

OP_TYPE_CATEGORIES = tuple(value.value for value in OpTypeCategory)


def supports_source(category, source):
    return source in ("internal", "external") and category in (source, "both")


def machine_types(machine: Any):
    read = machine.get if isinstance(machine, dict) else lambda key, default=None: getattr(machine, key, default)
    primary = read("op_type_id")
    additional = read("op_type_ids", ()) or ()
    return tuple(dict.fromkeys(([primary] if primary else []) + list(additional)))


def machine_type_index(machines, capabilities):
    result = {row["machine_id"]: set(machine_types(row)) for row in machines}
    for row in capabilities:
        result.setdefault(row["machine_id"], set()).add(row["op_type_id"])
    return result


def supplier_capability_rows(suppliers, bindings, status=None):
    """Effective supplier bindings from the current operation's original rows."""
    by_id = {row["supplier_id"]: row for row in suppliers}
    effective = {(row["supplier_id"], row["op_type_id"]): 0 for row in suppliers
                 if row["op_type_id"] is not None and row["op_type_id"] != ""}
    effective.update({(row["supplier_id"], row["op_type_id"]): 1 for row in bindings})
    result = []
    for (supplier_id, op_type_id), explicit in sorted(effective.items()):
        supplier = by_id.get(supplier_id)
        if status is not None and supplier is not None and supplier["status"] != status:
            continue
        result.append({"supplier_id": supplier_id, "op_type_id": op_type_id,
                       "default_days": supplier["default_days"] if supplier else None,
                       "status": supplier["status"] if supplier else None,
                       "explicit": explicit, "missing_supplier": supplier is None})
    return result
