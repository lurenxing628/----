"""Bounded projections have the exact existing domain write-state shape."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict

from .state_projection import machine_write_state, operator_write_state, supplier_write_state

if TYPE_CHECKING:
    from .table_facts import ResourceTableFacts


def resource_table_states(facts: ResourceTableFacts, kind, codes, *, dependencies=None):
    if kind in ("machine_group", "shift_profile"):
        return _catalog_states(facts, kind, codes)
    if kind not in ("machine", "operator", "supplier"):
        raise ValueError("Unsupported resource batch state")
    counts = facts.repo.assigned_counts(kind, codes) if dependencies is None else dependencies
    if kind == "supplier":
        return {code: _supplier_state(facts, code, counts[code]) for code in codes}
    patterns = {}
    if kind == "operator":
        profiles = facts.raw_lookup("operator_profiles", "operator_id")
        shifts = sorted({
            profiles[code]["shift_profile_id"]
            for code in codes
            if code in profiles and profiles[code]["shift_profile_id"] is not None
        })
        patterns = facts.shift_patterns(shifts)
    return {code: _resource_state(facts, kind, code, counts[code], patterns) for code in codes}


def _catalog_states(facts: ResourceTableFacts, kind, codes):
    counts = facts.repo.member_counts(kind, codes)
    patterns = facts.shift_patterns(codes) if kind == "shift_profile" else None
    result = {}
    for code in codes:
        state: Dict[str, Any] = {
            "identity": asdict(facts.identity(kind, code)),
            "record": facts.raw_record(kind, code),
            "member_count": counts[code],
        }
        if patterns is not None:
            state["pattern"] = patterns.get(code, [])
        result[code] = state
    return result


def _resource_state(facts: ResourceTableFacts, kind, code, counts, patterns):
    raw = facts.raw_record(kind, code)
    profile_name, key = ("groups", "machine_id") if kind == "machine" else ("operator_profiles", "operator_id")
    profile = facts.raw_lookup(profile_name, key).get(code)
    if kind == "machine":
        return machine_write_state(facts.identity(kind, code), raw, profile, counts,
                                   [facts.raw_related("op_type", item) for item in facts.machine_types(code)],
                                   facts.raw_related("machine_group", profile["group_id"]) if profile else None)
    skills = facts.grouped("skills", "operator_id")[code]
    authorizations = facts.grouped("authorizations", "operator_id")[code]
    shift = profile["shift_profile_id"] if profile else None
    return operator_write_state(facts.identity(kind, code), raw, profile, counts, skills,
                                [facts.raw_related("op_type", row["op_type_id"]) for row in skills], authorizations,
                                [facts.raw_related("machine", row["machine_id"]) for row in authorizations],
                                facts.raw_related("shift_profile", shift), patterns.get(shift, []))


def _supplier_state(facts: ResourceTableFacts, code, counts):
    identity = facts.identity("supplier", code)
    supplier: Dict[str, Any] = dict(facts.raw_record("supplier", code), ref=identity.ref, revision=identity.revision)
    supplier["profile"] = facts.raw_lookup("supplier_profiles", "supplier_id").get(code)
    op_types = []
    for key in facts.supplier_types(code):
        op_type = facts.identity("op_type", key)
        op_types.append(dict(facts.raw_record("op_type", key), ref=op_type.ref, revision=op_type.revision))
    supplier["op_types"] = op_types
    supplier["counts"] = counts
    return supplier_write_state(identity, supplier)
