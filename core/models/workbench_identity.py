"""Internal identity row. Revisions and database keys are not public DTO fields."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchEntityIdentity:
    ref: str
    kind: str
    entity_key: str
    revision: int
    active: bool
