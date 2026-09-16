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


def _compared_fields(current):
    """Internal rows compare hour quotas; external rows compare days and supplier."""
    quota_fields = ("setup_hours", "unit_hours") if current["source"] == "internal" else ("external_days", "supplier_ref")
    return ("label", "source", "op_type_ref") + quota_fields


def _row_updated(previous, current):
    """A matched before/after pair is updated when any compared field or its external group differs."""
    changed = any(previous[field] != current[field] for field in _compared_fields(current))
    previous_group, current_group = previous["external_group"], current["external_group"]
    changed |= any((previous_group or {}).get(field) != (current_group or {}).get(field) for field in ("merge_mode", "total_days"))
    return changed


def _change_state(previous, current):
    if previous is None:
        return "added"
    if current is None:
        return "removed"
    return "updated" if _row_updated(previous, current) else "unchanged"


def _change_counts(changes):
    return {state: sum(row["change"] == state for row in changes) for state in ("added", "removed", "updated", "unchanged")}


def _cleared_resources(before):
    """Manual machine/operator picks on the old rows are dropped together with the piece instances."""
    return [{"operation_ref": row["ref"], "sequence": row["sequence"], "business_code": row["business_code"],
             "machine": row["resources"]["machine"], "operator": row["resources"]["operator"]}
            for row in before if row["machine_ref"] is not None or row["operator_ref"] is not None]


def template_changes(before, after):
    """Piece instances are removed; the template creates one unsplit operation."""
    old = {(row["sequence"], row["piece_id"]): row for row in before}
    new = {(row["sequence"], None): row for row in after}
    changes = []
    for key in sorted(set(old) | set(new), key=lambda value: (value[0], value[1] or "")):
        previous, current = old.get(key), new.get(key)
        changes.append({"sequence": key[0], "piece_id": key[1], "change": _change_state(previous, current),
                        "before": previous, "after": current})
    cleared = _cleared_resources(before)
    return {"changes": changes, "change_counts": _change_counts(changes), "cleared_resources": cleared}
