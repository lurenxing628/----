"""Bounded projections have the exact existing domain write-state shape."""

from dataclasses import asdict

from core.models.workbench_supplier import supplier_state


def resource_table_states(facts, kind, codes):
    if kind == "supplier":
        references = facts.repo.page_relations(kind, codes)
        return {code: _supplier_state(facts, code, references) for code in codes}
    counts = facts.repo.assigned_counts(kind, codes)
    patterns = {}
    if kind == "operator":
        profiles = facts.mapped("operator_profiles", "operator_id")
        shifts = sorted({profiles[code]["shift_profile_id"] for code in codes if code in profiles and profiles[code]["shift_profile_id"] is not None})
        patterns = facts.repo.page_relations("shift_profile", shifts)["pattern"]
    return {code: _resource_state(facts, kind, code, counts[code], patterns) for code in codes}


def _resource_state(facts, kind, code, counts, patterns):
    raw = facts.records(kind)[code]
    profile_name, key = ("groups", "machine_id") if kind == "machine" else ("operator_profiles", "operator_id")
    profile = facts.mapped(profile_name, key).get(code)
    result = {"identity": asdict(facts.identity(kind, code)), "record": raw, "profile": profile, "dependencies": counts}
    if kind == "machine":
        result["op_type"] = facts.related("op_type", raw["op_type_id"])
        result["group"] = facts.related("machine_group", profile["group_id"]) if profile else None
    else:
        result["skills"] = facts.grouped("skills", "operator_id")[code]
        result["skill_types"] = [facts.related("op_type", row["op_type_id"]) for row in result["skills"]]
        result["machine_authorizations"] = facts.grouped("authorizations", "operator_id")[code]
        shift = profile["shift_profile_id"] if profile else None
        result["shift"] = facts.related("shift_profile", shift)
        result["shift_pattern"] = patterns.get(shift, [])
    return result


def _supplier_state(facts, code, references):
    identity = facts.identity("supplier", code)
    supplier = dict(facts.records("supplier")[code], ref=identity.ref, revision=identity.revision)
    supplier["profile"] = facts.mapped("supplier_profiles", "supplier_id").get(code)
    explicit = {row["op_type_id"] for row in facts.grouped("capabilities", "supplier_id")[code]}
    types = []
    for key in facts.supplier_types(code):
        related = facts.related("op_type", key)
        row = dict(related["record"], ref=related["identity"]["ref"], revision=related["identity"]["revision"])
        row.update({"legacy": int(key == supplier["op_type_id"]), "explicit": int(key in explicit)})
        types.append(row)
    supplier["op_types"] = types
    supplier["references"] = {name: rows.get(code, []) for name, rows in references.items()}
    return {"identity": asdict(identity), "supplier": supplier, "state": supplier_state(supplier["status"], supplier["profile"])}
