"""A work type can support two sources; each operation still chooses one."""


def supports_source(category, source):
    return source in ("internal", "external") and category in (source, "both")


def machine_type_index(machines, capabilities):
    """设备能做的工种只存在 MachineOpTypes：每台登记的设备都有键，能力集合可以为空。"""
    result = {row["machine_id"]: set() for row in machines}
    for row in capabilities:
        result[row["machine_id"]].add(row["op_type_id"])
    return result


def supplier_capability_rows(suppliers, bindings, status=None):
    """Supplier work-type bindings (WorkbenchSupplierOpTypes) joined with the current supplier rows."""
    by_id = {row["supplier_id"]: row for row in suppliers}
    result = []
    for supplier_id, op_type_id in sorted({(row["supplier_id"], row["op_type_id"]) for row in bindings}):
        supplier = by_id.get(supplier_id)
        if status is not None and supplier is not None and supplier["status"] != status:
            continue
        result.append({"supplier_id": supplier_id, "op_type_id": op_type_id,
                       "default_days": supplier["default_days"] if supplier else None,
                       "status": supplier["status"] if supplier else None,
                       "missing_supplier": supplier is None})
    return result
