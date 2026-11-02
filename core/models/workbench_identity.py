"""Internal identity row. Revisions and database keys are not public DTO fields."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchEntityIdentity:
    ref: str
    kind: str
    entity_key: str
    revision: int
    active: bool


def is_entity_ref(value) -> bool:
    return type(value) is str and len(value) == 48 and all(c in "0123456789abcdef" for c in value)
