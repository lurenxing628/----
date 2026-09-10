"""Private permanent-reference lookup contracts; never confer write permission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class WorkbenchPlanLocator:
    version: int
    plan_role: str
    scenario_id: Optional[str] = None


class WorkbenchPlanReferenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WorkbenchPlanReferenceIssue:
    code: str
    message: str


@dataclass(frozen=True)
class WorkbenchPlanCatalogReference:
    plan_ref: Optional[str]
    binding_valid: bool
    issues: Tuple[WorkbenchPlanReferenceIssue, ...] = ()
