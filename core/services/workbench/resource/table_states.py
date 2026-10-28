"""Bounded projections have the exact existing domain write-state shape."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .state_projection import machine_write_state, operator_write_state, supplier_write_state

if TYPE_CHECKING:
    from .table_facts import ResourceTableFacts


def resource_table_states(facts: ResourceTableFacts, kind, codes, *, dependencies=None, supplier_references=None):
    if kind == "supplier":
        references = facts.repo.page_relations(kind, codes) if supplier_references is None else supplier_references
        return {code: _supplier_state(facts, code, references) for code in codes}
    if kind in ("machine_group", "shift_profile"):
        return _catalog_states(facts, kind, codes)
    if kind not in ("machine", "operator"):
        raise ValueError("Unsupported resource batch state")
    counts = facts.assigned_counts(kind, codes) if dependencies is None else dependencies
    patterns = {}
    if kind == "operator":
        profiles = facts.raw_lookup("operator_profiles", "operator_id")
        shifts = sorted({profiles[code]["shift_profile_id"] for code in codes if code in profiles and profiles[code]["shift_profile_id"] is not None})
        patterns = facts.shift_patterns(shifts)
    return {code: _resource_state(facts, kind, code, counts[code], patterns) for code in codes}


def _catalog_states(facts: ResourceTableFacts, kind, codes):
    if kind == "machine_group":
        memberships, member_key = facts.grouped("groups", "group_id"), "machine_id"
        patterns = None
    else:
        memberships, member_key = facts.grouped("operator_profiles", "shift_profile_id"), "operator_id"
        patterns = facts.shift_patterns(codes)
    result = {}
    for code in codes:
        state = {"identity": asdict(facts.identity(kind, code)), "record": facts.raw_record(kind, code)}
        if patterns is not None:
            state["pattern"] = patterns.get(code, [])
        state["members"] = [{member_key: row[member_key]} for row in memberships[code]]
        result[code] = state
    return result


def _resource_state(facts: ResourceTableFacts, kind, code, counts, patterns):
    raw = facts.raw_record(kind, code)
    profile_name, key = ("groups", "machine_id") if kind == "machine" else ("operator_profiles", "operator_id")
    profile = facts.raw_lookup(profile_name, key).get(code)
    if kind == "machine":
        types = ({row["op_type_id"] for row in facts.grouped("machine_capabilities", "machine_id")[code]}
                 | ({raw["op_type_id"]} if raw["op_type_id"] is not None else set()))
        return machine_write_state(facts.identity(kind, code), raw, profile, counts,
                                   [facts.raw_related("op_type", item) for item in sorted(types)],
                                   facts.raw_related("machine_group", profile["group_id"]) if profile else None)
    skills = facts.grouped("skills", "operator_id")[code]
    authorizations = facts.grouped("authorizations", "operator_id")[code]
    shift = profile["shift_profile_id"] if profile else None
    return operator_write_state(facts.identity(kind, code), raw, profile, counts, skills,
                                [facts.raw_related("op_type", row["op_type_id"]) for row in skills], authorizations,
                                [facts.raw_related("machine", row["machine_id"]) for row in authorizations],
                                facts.raw_related("shift_profile", shift), patterns.get(shift, []))


def _supplier_state(facts: ResourceTableFacts, code, references):
    identity = facts.identity("supplier", code)
    supplier: dict[str, Any] = dict(facts.raw_record("supplier", code), ref=identity.ref, revision=identity.revision)
    supplier["profile"] = facts.raw_lookup("supplier_profiles", "supplier_id").get(code)
    types = []
    for key in sorted({row["op_type_id"] for row in facts.grouped("capabilities", "supplier_id")[code]}):
        related = facts.raw_related("op_type", key)
        if related is not None:
            types.append(dict(related["record"], ref=related["identity"]["ref"], revision=related["identity"]["revision"]))
    supplier["op_types"] = types
    supplier["references"] = {name: rows.get(code, []) for name, rows in references.items()}
    return supplier_write_state(identity, supplier)
