"""Explain template replacement from the exact before/after rows."""

import math

from core.models.workbench_batch import MAX_INTEGER


def _display_number(value):
    # Non-applicable legacy fields stay untouched in storage and cannot break JSON.
    return value if type(value) in (int, float) and math.isfinite(value) and abs(value) <= MAX_INTEGER else None


def template_after(rows, facts, projection):
    groups = {row["group_id"]: row for row in facts["ExternalGroups"]}
    result = []
    for row in sorted(rows, key=lambda item: (item["seq"], item["id"])):
        group = groups.get(row["ext_group_id"])
        result.append({"sequence": row["seq"], "label": row["op_type_name"], "source": row["source"],
                       "op_type_ref": projection.ref("op_type", row["op_type_id"]),
                       "setup_hours": _display_number(row["setup_hours"]), "unit_hours": _display_number(row["unit_hours"]), "external_days": _display_number(row["ext_days"]),
                       "external_group": {"merge_mode": group["merge_mode"], "total_days": _display_number(group["total_days"])} if group else None,
                       "machine_ref": None, "operator_ref": None,
                       "supplier_ref": projection.ref("supplier", row["supplier_id"]),
                       "supplier": projection.resource("supplier", row["supplier_id"])})
    return result


def template_changes(before, after):
    """Piece instances are removed; the template creates one unsplit operation."""
    old = {(row["sequence"], row["piece_id"]): row for row in before}
    new = {(row["sequence"], None): row for row in after}
    fields = ("label", "source", "op_type_ref")
    changes = []
    for key in sorted(set(old) | set(new), key=lambda value: (value[0], value[1] or "")):
        previous, current = old.get(key), new.get(key)
        state = "added" if previous is None else "removed" if current is None else "unchanged"
        if previous is not None and current is not None:
            quota_fields = ("setup_hours", "unit_hours") if current["source"] == "internal" else ("external_days", "supplier_ref")
            changed = any(previous[field] != current[field] for field in fields + quota_fields)
            previous_group, current_group = previous["external_group"], current["external_group"]
            changed |= any((previous_group or {}).get(field) != (current_group or {}).get(field) for field in ("merge_mode", "total_days"))
            if changed:
                state = "updated"
        changes.append({"sequence": key[0], "piece_id": key[1], "change": state,
                        "before": previous, "after": current})
    cleared = [{"operation_ref": row["ref"], "sequence": row["sequence"], "business_code": row["business_code"],
                "machine": row["resources"]["machine"], "operator": row["resources"]["operator"]}
               for row in before if row["machine_ref"] is not None or row["operator_ref"] is not None]
    return {"changes": changes, "change_counts": {state: sum(row["change"] == state for row in changes)
            for state in ("added", "removed", "updated", "unchanged")}, "cleared_resources": cleared}
