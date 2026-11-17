"""Prepare the final operator-machine relations before writing any row."""

from dataclasses import dataclass

from core.models.operator_machine import OperatorMachine


@dataclass(frozen=True)
class OperatorMachineChanges:
    removed: tuple
    updated: tuple
    added: tuple


def prepare_operator_machine_changes(current_rows, requested, *, removed=()):
    """主操是每条关联自己的属性：最终关系就是请求值，不牵动同一个人的其他设备，只写实际变化。"""
    original = {(row["operator_id"], row["machine_id"]):
                {"skill_level": row["skill_level"], "is_primary": row["is_primary"]}
                for row in current_rows}
    final = dict(original)
    for key in removed:
        final.pop(key, None)
    for link in requested:
        final[(link.operator_id, link.machine_id)] = {"skill_level": link.skill_level, "is_primary": link.is_primary}
    updated, added = [], []
    for key, fields in sorted(final.items()):
        before = original.get(key)
        if before != fields:
            link = OperatorMachine(key[0], key[1], **fields)
            (added if before is None else updated).append(link)
    return OperatorMachineChanges(tuple(sorted(set(original) - set(final))), tuple(updated), tuple(added))
