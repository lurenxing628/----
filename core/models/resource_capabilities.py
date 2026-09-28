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
