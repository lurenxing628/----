"""Prepare the final operator-machine relations before writing any row."""

from dataclasses import dataclass

from core.models.operator_machine import OperatorMachine

from .operator_machine_normalizers import normalize_yes_no_stored


@dataclass(frozen=True)
class OperatorMachineChanges:
    removed: tuple
    updated: tuple
    added: tuple


def _is_primary(value):
    return value == "yes" or (value != "no" and normalize_yes_no_stored(value) == "yes")


def prepare_operator_machine_changes(current_rows, requested, *, removed=(), primaries=None):
    """Keep only actual changes, with the last requested primary winning for its operator."""
    original = {(row["operator_id"], row["machine_id"]):
                {"skill_level": row["skill_level"], "is_primary": row["is_primary"]}
                for row in current_rows}
    final = dict(original)
    selected_primaries = {}
    for key, fields in original.items():
        if _is_primary(fields["is_primary"]):
            selected_primaries.setdefault(key[0], set()).add(key[1])
    for key in removed:
        final.pop(key, None)
        selected_primaries.get(key[0], set()).discard(key[1])
    if primaries is not None:
        for operator_id, allowed in primaries.items():
            for machine_id in selected_primaries.get(operator_id, set()) - set(allowed):
                other = (operator_id, machine_id)
                final[other] = dict(final[other], is_primary="no")
        for link in requested:
            final[(link.operator_id, link.machine_id)] = {
                "skill_level": link.skill_level,
                "is_primary": link.is_primary,
            }
    else:
        for link in requested:
            key = (link.operator_id, link.machine_id)
            selected = selected_primaries.setdefault(link.operator_id, set())
            if _is_primary(link.is_primary):
                for machine_id in selected - {link.machine_id}:
                    other = (link.operator_id, machine_id)
                    final[other] = dict(final[other], is_primary="no")
                selected.clear()
                selected.add(link.machine_id)
            else:
                selected.discard(link.machine_id)
            final[key] = {"skill_level": link.skill_level, "is_primary": link.is_primary}
    updated, added = [], []
    for key, fields in sorted(final.items()):
        before = original.get(key)
        if before != fields:
            link = OperatorMachine(key[0], key[1], **fields)
            (added if before is None else updated).append(link)
    return OperatorMachineChanges(tuple(sorted(set(original) - set(final))), tuple(updated), tuple(added))
