"""Public flat fields separate from full private domain conflict evidence."""

import re

from core.models.workbench_resource_file import file_columns
from core.models.workbench_resource_status import public_resource_status
from core.services.workbench import messages

# 数据库里的创建/更新时间按 UTC 存，给用户看和写进文件前统一换算过来。
_STORED_TIMES = ("created_at", "updated_at")
_STORED_TIME_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")


def _local_time(value):
    """能认出来的存储时刻换算给用户看；认不出的旧值原样保留，不猜着换算也不改写。"""
    if type(value) is not str or _STORED_TIME_TEXT.match(value) is None:
        return value
    try:
        return messages.stored_utc_text(value)
    except (ValueError, OverflowError):
        # 形似时刻却不是真实日期（例如 2026-02-30 08:00），或换算后越过 9999 年（9999-12-31 16:00 以后），同样原样保留
        return value


def resource_export_state(facts, kind, code):
    """Use captured file fields without loading write-conflict dependencies."""
    raw = facts.raw_record(kind, code)
    if kind == "supplier":
        return _supplier_export_state(facts, code, raw)
    state = {"record": raw}
    if kind == "op_type":
        state["profile"] = facts.raw_lookup("policies", "op_type_id").get(code)
    elif kind == "machine":
        profile = facts.raw_lookup("groups", "machine_id").get(code)
        types = {row["op_type_id"] for row in facts.grouped("machine_capabilities", "machine_id")[code]}
        if raw["op_type_id"] is not None:
            types.add(raw["op_type_id"])
        state["op_types"] = [facts.raw_related("op_type", item) for item in sorted(types)]
        state["group"] = facts.raw_related("machine_group", profile["group_id"]) if profile else None
    elif kind == "operator":
        state["profile"] = facts.raw_lookup("operator_profiles", "operator_id").get(code)
        state["skills"] = facts.grouped("skills", "operator_id")[code]
        profile = state["profile"]
        shift = profile["shift_profile_id"] if profile else None
        state["shift"] = facts.raw_related("shift_profile", shift)
        # The file includes these relationships; keep the same missing-resource rejection.
        for row in state["skills"]:
            facts.identity("op_type", row["op_type_id"])
            facts.raw_record("op_type", row["op_type_id"])
        for row in facts.grouped("authorizations", "operator_id")[code]:
            facts.identity("machine", row["machine_id"])
            facts.raw_record("machine", row["machine_id"])
    return state


def _supplier_export_state(facts, code, raw):
    explicit = {row["op_type_id"] for row in facts.grouped("capabilities", "supplier_id")[code]}
    legacy = raw["op_type_id"]
    types = []
    for key in sorted(explicit | ({legacy} if legacy not in (None, "") else set())):
        related = facts.raw_related("op_type", key)
        types.append({"op_type_id": related["identity"]["entity_key"], "explicit": int(key in explicit)})
    supplier = dict(raw, profile=facts.raw_lookup("supplier_profiles", "supplier_id").get(code), op_types=types)
    return {"supplier": supplier}


def _related_code(value):
    return value["identity"]["entity_key"] if value else None


def _authorization(row):
    return {"machine_code": row["machine_id"], "operator_code": row["operator_id"],
            "skill_level": row["skill_level"], "is_primary": row["is_primary"],
            "created_at": _local_time(row["created_at"])}


def flat_resource(kind, identity, state, authorizations=()):
    raw = state["supplier"] if kind == "supplier" else state["record"]
    result = {key: raw.get(key) for key in file_columns(kind)}
    result.update({key: _local_time(result[key]) for key in _STORED_TIMES if key in result})
    result.update(business_code=identity.entity_key, label=raw["name"])
    if kind == "op_type":
        result["default_merge_mode"] = state["profile"]["default_merge_mode"] if state["profile"] else None
    else:
        profile = raw["profile"] if kind == "supplier" else state.get("profile")
        result.update(status=public_resource_status(kind, raw["status"], profile), legacy_status=raw["status"])
    if kind in ("machine", "operator"):
        result["team_code"] = raw["team_id"]
        result["machine_authorizations"] = [_authorization(row) for row in authorizations]
    if kind == "machine":
        result.update(op_type_code=raw["op_type_id"], group_code=_related_code(state["group"]),
                      op_type_codes=[item["identity"]["entity_key"] for item in state["op_types"]])
    if kind == "operator":
        result.update(_operator_fields(state))
    if kind == "supplier":
        result.update(_supplier_fields(raw))
    return result


def _operator_fields(state):
    return {"skill_codes": [row["op_type_id"] for row in state["skills"]],
            "shift_profile_code": _related_code(state["shift"]),
            "skills_declared": bool(state["skills"] or (state["profile"] and state["profile"]["skills_declared"])),
            "inactive_reason": state["profile"]["inactive_reason"] if state["profile"] else None,
            "skill_details": [{"op_type_code": row["op_type_id"], "skill_level": row["skill_level"],
                               "is_primary": row["is_primary"], "created_at": _local_time(row["created_at"])}
                              for row in state["skills"]]}


def _supplier_fields(raw):
    return {"op_type_codes": [row["op_type_id"] for row in raw["op_types"]],
            "explicit_op_type_codes": [row["op_type_id"] for row in raw["op_types"] if row["explicit"]],
            "legacy_op_type_code": raw["op_type_id"],
            "inactive_reason": raw["profile"]["inactive_reason"] if raw["profile"] else None}


def reference_count(expected):
    return sum(len(rows) for rows in expected["references"].values())
