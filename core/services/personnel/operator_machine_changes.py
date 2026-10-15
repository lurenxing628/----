"""Prepare the final operator-machine relations before writing any row."""

from dataclasses import dataclass

from core.models import OperatorMachine

from .operator_machine_normalizers import normalize_yes_no_stored


@dataclass(frozen=True)
class OperatorMachineChanges:
    removed: tuple
    updated: tuple
    added: tuple


def _is_primary(value):
    return value == "yes" or (value != "no" and normalize_yes_no_stored(value) == "yes")


def prepare_operator_machine_changes(current_rows, requested, *, removed=()):
    """Keep only actual changes, with the last requested primary winning for its operator."""
    original = {(row["operator_id"], row["machine_id"]):
                {"skill_level": row["skill_level"], "is_primary": row["is_primary"]}
                for row in current_rows}
    final = dict(original)
    primaries = {}
    for key, fields in original.items():
        if _is_primary(fields["is_primary"]):
            primaries.setdefault(key[0], set()).add(key[1])
    for key in removed:
        final.pop(key, None)
        primaries.get(key[0], set()).discard(key[1])
    for link in requested:
        key = (link.operator_id, link.machine_id)
        selected = primaries.setdefault(link.operator_id, set())
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
            link = OperatorMachine(None, key[0], key[1], **fields)
            (added if before is None else updated).append(link)
    return OperatorMachineChanges(tuple(sorted(set(original) - set(final))), tuple(updated), tuple(added))
