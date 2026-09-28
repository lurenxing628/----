"""Stable identity for one captured external group, independent of scheduling."""

import hashlib
import json


def context_group_key(row):
    if row["group_id"] is None:
        return None
    values = [row[key] for key in ("group_ref", "group_part_no", "start_sequence", "end_sequence",
                                  "merge_mode", "supplier_id")]
    values.append(row["total_days"] if row["merge_mode"] == "merged" else None)
    encoded = json.dumps(values, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return row["group_ref"] + ":" + hashlib.sha256(encoded.encode("ascii")).hexdigest()[:16]
