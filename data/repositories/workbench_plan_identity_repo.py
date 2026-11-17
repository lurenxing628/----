"""SELECT-only permanent refs. Caller owns the connection and read snapshot.

These locators identify stored objects, not complete/executable plans. Continue
using the existing plan catalog/identity service for completeness and capability.
No missing mapping is repaired, no stale ref is rebound, and no latest fallback
exists. Bulk methods are all-or-error via single json_each(?) queries.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, NoReturn

from core.models.schedule_plan_role import ROLE_ADOPTED, VALID_PLAN_ROLES
from core.models.workbench_plan_reference import (
    WorkbenchPlanLocator,
    WorkbenchPlanReferenceError,
)
from core.shared.refs import is_ref
from core.shared.strict_parse import is_exact_positive_int

from .base_repo import BaseRepository


def fail_plan_reference(code: str) -> NoReturn:
    messages = {
        "reference_not_found": "所选计划引用不存在或已失效。",
        "identity_missing": "永久身份缺失，不能读取或自动补建。",
        "plan_binding_invalid": "计划身份绑定不完整或已经改变。",
        "task_binding_invalid": "任务不属于所选计划或原工序实例已经改变。",
    }
    raise WorkbenchPlanReferenceError(code, messages[code])


def require_plan_ref_format(plan_ref: object) -> str:
    if not is_ref(plan_ref):
        fail_plan_reference("reference_not_found")
    return plan_ref


def validate_plan_locator(value: Any) -> WorkbenchPlanLocator:
    version, role = value.version, value.plan_role
    if not is_exact_positive_int(version) or role not in VALID_PLAN_ROLES:
        fail_plan_reference("plan_binding_invalid")
    return WorkbenchPlanLocator(version, role)


class WorkbenchPlanIdentityRepository(BaseRepository):
    def read_revision(self) -> int:
        """The clock of the identity source tables only; its DDL admits only a positive integer."""
        revision = self.fetchvalue("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton = 1")
        if revision is None:
            fail_plan_reference("identity_missing")
        return revision

    def fetch_plan_locator(self, ref: str) -> WorkbenchPlanLocator:
        row = self.fetchone("SELECT version FROM ScheduleHistory WHERE plan_ref = ?", (ref,))
        if row is None:
            fail_plan_reference("reference_not_found")
        return WorkbenchPlanLocator(row["version"], ROLE_ADOPTED)

    def resolve_plan(self, plan_ref: object) -> WorkbenchPlanLocator:
        ref = require_plan_ref_format(plan_ref)
        self.read_revision()
        return self.fetch_plan_locator(ref)

    def fetch_plan_ref(self, normalized: WorkbenchPlanLocator) -> str:
        row = self.fetchone("SELECT plan_ref FROM ScheduleHistory WHERE version = ?", (normalized.version,))
        if row is None:
            fail_plan_reference("identity_missing")
        return row["plan_ref"]

    def get_plan_ref(self, locator: Any) -> str:
        normalized = validate_plan_locator(locator)
        self.read_revision()
        return self.fetch_plan_ref(normalized)

    def get_operation_refs(self, ids: Iterable[int]) -> Dict[int, str]:
        values = list(ids)
        if not values:
            return {}
        self.read_revision()
        if any(not is_exact_positive_int(key) for key in values):
            fail_plan_reference("task_binding_invalid")
        rows = self.fetchall(
            """
            SELECT bo.id, m.ref
            FROM BatchOperations bo
            JOIN WorkbenchPlanSourceRefs m
              ON m.kind = 'operation'
             AND m.active = 1
             AND m.source_key = CAST(bo.id AS TEXT)
            WHERE bo.id IN (SELECT value FROM json_each(?))
            """,
            (json.dumps(values),),
        )
        output = {row["id"]: row["ref"] for row in rows}
        if any(key not in output for key in values):
            fail_plan_reference("identity_missing")
        return output
