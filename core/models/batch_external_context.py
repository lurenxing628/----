"""Stable identity for one captured external group, independent of scheduling."""

from core.models.content import content_text


def context_group_key(row):
    if row["group_id"] is None:
        return None
    values = [row[key] for key in ("group_ref", "group_part_no", "start_sequence", "end_sequence",
                                  "merge_mode", "supplier_id")]
    values.append(row["total_days"] if row["merge_mode"] == "merged" else None)
    return content_text(values)
