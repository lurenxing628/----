"""Private permanent-reference lookup contracts; never confer write permission."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchPlanLocator:
    version: int
    plan_role: str = "adopted"


class WorkbenchPlanReferenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
