"""Bounded projections have the exact existing domain write-state shape."""

from .state_projection import machine_write_state, operator_write_state, supplier_write_state


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
    if kind == "machine":
        types = set(facts.machine_types(code)) | ({raw["op_type_id"]} if raw["op_type_id"] is not None else set())
        return machine_write_state(facts.identity(kind, code), raw, profile, counts,
                                   [facts.related("op_type", item) for item in sorted(types)],
                                   facts.related("machine_group", profile["group_id"]) if profile else None)
    skills = facts.grouped("skills", "operator_id")[code]
    authorizations = facts.grouped("authorizations", "operator_id")[code]
    shift = profile["shift_profile_id"] if profile else None
    return operator_write_state(facts.identity(kind, code), raw, profile, counts, skills,
                                [facts.related("op_type", row["op_type_id"]) for row in skills], authorizations,
                                [facts.related("machine", row["machine_id"]) for row in authorizations],
                                facts.related("shift_profile", shift), patterns.get(shift, []))


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
    return supplier_write_state(identity, supplier)
