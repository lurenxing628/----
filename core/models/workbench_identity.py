"""Internal identity row. Revisions and database keys are not public DTO fields."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchEntityIdentity:
    ref: str
    kind: str
    entity_key: str
    revision: int
    active: bool

    @classmethod
    def from_row(cls, row) -> "WorkbenchEntityIdentity":
        """The one WorkbenchEntityRefs row (ref, kind, entity_key, revision, active) -> identity mapping.

        The table's CHECKs pin revision to a positive integer and active to 0/1, so only active is converted."""
        return cls(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"]))
