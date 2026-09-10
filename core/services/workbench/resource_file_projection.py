"""Public flat fields separate from full private domain conflict evidence."""

from core.models.workbench_resource_file import file_columns
from core.services.workbench.resource_projection import project_resource


def resource_file_state(reader, repo, identity):
    state = reader.domain.snapshot(identity)
    return {"state": state, "references": repo.references(reader.kind, identity.entity_key)}


def _related_code(value):
    return value["identity"]["entity_key"] if value else None


def _authorization(row):
    return {"machine_code": row["machine_id"], "operator_code": row["operator_id"],
            **{key: row[key] for key in ("skill_level", "is_primary", "created_at")}}


def flat_resource(kind, identity, expected, repo):
    state = expected["state"]
    raw = state["supplier"] if kind == "supplier" else state["record"]
    entity = project_resource(kind, identity, state)
    result = {key: raw.get(key) for key in file_columns(kind)}
    result.update(business_code=identity.entity_key, label=raw["name"])
    if kind == "op_type":
        result["default_merge_mode"] = entity["fields"]["default_merge_mode"]
    else:
        result.update(status=entity["status"], legacy_status=raw["status"])
    if kind in ("machine", "operator"):
        result["team_code"] = raw["team_id"]
        result["machine_authorizations"] = [_authorization(row) for row in repo.authorizations(kind, identity.entity_key)]
    if kind == "machine":
        result.update(op_type_code=raw["op_type_id"], group_code=_related_code(state["group"]))
    if kind == "operator":
        result.update(_operator_fields(state, entity))
    if kind == "supplier":
        result.update(_supplier_fields(raw))
    return result


def _operator_fields(state, entity):
    return {"skill_codes": [row["op_type_id"] for row in state["skills"]],
            "shift_profile_code": _related_code(state["shift"]),
            "skills_declared": entity["relationships"]["skills_declared"],
            "inactive_reason": state["profile"]["inactive_reason"] if state["profile"] else None,
            "skill_details": [{"op_type_code": row["op_type_id"],
                               **{key: row[key] for key in ("skill_level", "is_primary", "created_at")}}
                              for row in state["skills"]]}


def _supplier_fields(raw):
    return {"op_type_codes": [row["op_type_id"] for row in raw["op_types"]],
            "explicit_op_type_codes": [row["op_type_id"] for row in raw["op_types"] if row["explicit"]],
            "legacy_op_type_code": raw["op_type_id"],
            "inactive_reason": raw["profile"]["inactive_reason"] if raw["profile"] else None}


def reference_count(expected):
    return sum(len(rows) for rows in expected["references"].values())
