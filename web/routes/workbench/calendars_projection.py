"""Public global-calendar DTOs; private revisions and tombstones stay server-side."""

from typing import Any, Dict

_STATE_FIELDS = ("date", "explicit", "calendar_ref", "revision", "row", "identity", "history", "effective")
_STORED_FIELDS = ("day_type", "shift_start", "shift_end", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "remark")


def calendar_snapshot(day: Dict[str, Any]) -> Dict[str, Any]:
    """Exclude month decorations/the clock from the authoritative edit binding."""
    return {key: day[key] for key in _STATE_FIELDS}


def calendar_policy(state: Dict[str, Any]) -> Dict[str, Any]:
    effective, row = dict(state["effective"]), state["row"]
    fields = {key: effective[key] for key in ("type", "hours", "eff", "allowNormal", "allowUrgent")}
    # A configured workday with both priorities disabled is stopped, not a holiday edit.
    if row is not None and row["day_type"] == "workday":
        fields["type"] = "work"
    fields["note"] = row["remark"] if row is not None else None
    return {"explicit": state["explicit"], "fields": fields, "effective": effective,
            "stored": {key: row[key] for key in _STORED_FIELDS} if row is not None else None}


def calendar_day(state: Dict[str, Any]) -> Dict[str, Any]:
    public = {"date": state["date"], "calendar_ref": state["calendar_ref"], **calendar_policy(state)}
    public["entity"] = None if not state["explicit"] else {
        "ref": state["calendar_ref"], "business_code": state["date"], "label": state["date"],
        "status": "configured", "fields": dict(public["fields"]), "relationships": {}, "issues": []}
    return public


def calendar_preview(preview) -> Dict[str, Any]:
    days = [{"date": item["date"], "before": calendar_day(item["before"]),
             "after": calendar_policy(item["after"]),
             "changed": item["before"]["row"] != item["after"]["row"]} for item in preview.days]
    changed = sum(item["changed"] for item in days)
    return {"preview_ref": preview.preview_ref, "created_at": preview.created_at, "expires_at": preview.expires_at,
            "request": {**preview.request, "fields": dict(preview.request["fields"])},
            "dates": list(preview.dates), "days": days,
            "counts": {"selected": len(days), "changed": changed, "unchanged": len(days) - changed,
                       "configured_before": sum(item["before"]["explicit"] for item in days),
                       "configured_after": sum(item["after"]["explicit"] for item in days)}}
