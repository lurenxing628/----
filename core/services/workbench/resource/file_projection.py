"""Public flat fields separate from full private domain conflict evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.workbench_resource_file import file_columns
from core.models.workbench_resource_status import public_resource_status
from core.services.workbench.material.files import local_created_at

if TYPE_CHECKING:
    from .table_facts import ResourceTableFacts

# 数据库里的创建/更新时间按 UTC 存，给用户看和写进文件前统一换算过来。
_STORED_TIMES = ("created_at", "updated_at")


def resource_export_state(facts: ResourceTableFacts, kind, code):
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


def _supplier_export_state(facts: ResourceTableFacts, code, raw):
    types = []
    for key in sorted({row["op_type_id"] for row in facts.grouped("capabilities", "supplier_id")[code]}):
        related = facts.raw_related("op_type", key)
        if related is not None:
            types.append({"op_type_id": related["identity"]["entity_key"]})
    supplier = dict(raw, profile=facts.raw_lookup("supplier_profiles", "supplier_id").get(code), op_types=types)
    return {"supplier": supplier}


def _related_code(value):
    return value["identity"]["entity_key"] if value else None


def _authorization(row):
    return {"machine_code": row["machine_id"], "operator_code": row["operator_id"],
            "skill_level": row["skill_level"], "is_primary": row["is_primary"],
            "created_at": local_created_at(row["created_at"])}


def flat_resource(kind, identity, state, authorizations=()):
    raw = state["supplier"] if kind == "supplier" else state["record"]
    result = {key: raw.get(key) for key in file_columns(kind)}
    result.update({key: local_created_at(result[key]) for key in _STORED_TIMES if key in result})
    result.update(business_code=identity.entity_key, label=raw["name"])
    if kind == "op_type":
        result["default_merge_mode"] = state["profile"]["default_merge_mode"] if state["profile"] else None
    else:
        profile = raw["profile"] if kind == "supplier" else state.get("profile")
        result["status"] = public_resource_status(kind, raw["status"], profile)
    if kind in ("machine", "operator"):
        result["team_code"] = raw["team_id"]
        result["machine_authorizations"] = [_authorization(row) for row in authorizations]
    if kind == "machine":
        result.update(group_code=_related_code(state["group"]),
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
                               "is_primary": row["is_primary"], "created_at": local_created_at(row["created_at"])}
                              for row in state["skills"]]}


def _supplier_fields(raw):
    return {"op_type_codes": [row["op_type_id"] for row in raw["op_types"]],
            "inactive_reason": raw["profile"]["inactive_reason"] if raw["profile"] else None}


def reference_count(expected):
    return sum(len(rows) for rows in expected["references"].values())
