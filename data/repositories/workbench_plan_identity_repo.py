"""SELECT-only permanent refs. Caller owns the connection and read snapshot.

These locators identify stored objects, not complete/executable plans. Continue
using the existing plan catalog/identity service for completeness and capability.
No missing mapping is repaired, no stale ref is rebound, and no latest fallback
exists. Bulk methods are all-or-error, with bounded SQL parameter chunks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, NoReturn, Optional, Sequence, Tuple

from core.models.schedule_plan_role import VALID_PLAN_ROLES
from core.models.workbench_plan_reference import (
    WorkbenchPlanCatalogReference,
    WorkbenchPlanLocator,
    WorkbenchPlanReferenceError,
    WorkbenchPlanReferenceIssue,
)
from core.shared.strict_parse import is_exact_positive_int

from .base_repo import BaseRepository

_REF_PATTERN = re.compile(r"[0-9a-f]{48}\Z")


def fail_plan_reference(code: str) -> NoReturn:
    messages = {
        "reference_not_found": "所选计划引用不存在或已失效。",
        "identity_missing": "永久身份缺失，不能读取或自动补建。",
        "plan_binding_invalid": "计划身份绑定不完整或已经改变。",
        "task_binding_invalid": "任务不属于所选计划或原工序实例已经改变。",
    }
    raise WorkbenchPlanReferenceError(code, messages[code])


def catalog_failure(
    code: str, message: str, plan_ref: Optional[str] = None,
) -> WorkbenchPlanCatalogReference:
    return WorkbenchPlanCatalogReference(plan_ref, False, (WorkbenchPlanReferenceIssue(code, message),))


def valid_plan_ref_format(plan_ref: object) -> bool:
    return isinstance(plan_ref, str) and _REF_PATTERN.fullmatch(plan_ref) is not None


def require_plan_ref_format(plan_ref: object) -> str:
    if not isinstance(plan_ref, str) or _REF_PATTERN.fullmatch(plan_ref) is None:
        fail_plan_reference("reference_not_found")
    return plan_ref


def catalog_identity_matches(record: Mapping[str, Any], locator: WorkbenchPlanLocator) -> bool:
    return (valid_plan_ref_format(record["ref"])
            and (record["version"], record["plan_role"]) == (locator.version, locator.plan_role)
            and record["kind"] == "official" and record["source_table"] == "schedule")


def requested_task_ids(rows: Iterable[Tuple[Any, Any, Any]], target_version: int) -> Dict[int, int]:
    expected: Dict[int, int] = {}
    for row_id, op_id, version in rows:
        if not all(is_exact_positive_int(value) for value in (row_id, op_id, version)) or version != target_version:
            fail_plan_reference("task_binding_invalid")
        if row_id in expected and expected[row_id] != op_id:
            fail_plan_reference("task_binding_invalid")
        expected[row_id] = op_id
    return expected


def validate_plan_locator(value: Any) -> WorkbenchPlanLocator:
    version, role = value.version, value.plan_role
    if not is_exact_positive_int(version) or role not in VALID_PLAN_ROLES:
        fail_plan_reference("plan_binding_invalid")
    return WorkbenchPlanLocator(version, role)


def extract_task_refs(
    ids: Sequence[int],
    expected: Mapping[int, int],
    target_version: int,
    captured: Mapping[int, Sequence[Mapping[str, Any]]],
    operation_refs_out: Optional[Dict[int, Optional[str]]] = None,
) -> Dict[int, str]:
    output: Dict[int, str] = {}
    for key in ids:
        for row in captured[key]:
            if row["op_id"] != expected[row["id"]] or row["operation_id"] != row["op_id"]:
                fail_plan_reference("task_binding_invalid")
            if row["mapped_version"] != target_version:
                fail_plan_reference("task_binding_invalid")
            if not row["operation_ref"] or row["operation_ref"] != row["current_operation_ref"]:
                fail_plan_reference("task_binding_invalid")
            if row["task_ref"] is None:
                fail_plan_reference("identity_missing")
            output[row["id"]] = row["task_ref"]
            if operation_refs_out is not None:
                operation_refs_out[row["op_id"]] = row["current_operation_ref"]
    if len(output) != len(expected):
        fail_plan_reference("task_binding_invalid")
    return output


class WorkbenchPlanIdentityRepository(BaseRepository):
    def read_revision(self) -> int:
        """Validate the identity clock and return the clock of the identity source tables only."""
        revision = self.fetchvalue("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton = 1")
        if not is_exact_positive_int(revision):
            fail_plan_reference("identity_missing")
        return revision

    def history_exists(self, version: int) -> bool:
        return self.fetchone("SELECT 1 FROM ScheduleHistory WHERE version = ? LIMIT 1", (version,)) is not None

    def source_row(self, kind: str, key: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            "SELECT * FROM WorkbenchPlanSourceRefs WHERE kind = ? AND source_key = ? AND active = 1",
            (kind, key),
        )

    def source_row_by_ref(self, plan_ref: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref = ? AND active = 1", (plan_ref,))

    def operation_ref_rows(self, chunk: Sequence[int]) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in chunk)
        return self.fetchall(
            "SELECT bo.id, m.ref FROM BatchOperations bo "
            "CROSS JOIN WorkbenchPlanSourceRefs m ON m.kind = 'operation' AND m.active = 1 "
            f"AND m.source_key = CAST(+bo.id AS TEXT) WHERE bo.id IN ({marks})",
            chunk,
        )

    def task_ref_rows(self, record: Mapping[str, Any], ids: Sequence[int]) -> List[Dict[str, Any]]:
        params = [record["ref"], *ids, record["version"]]
        marks = ",".join("?" for _ in ids)
        return self.fetchall(f"""SELECT s.id, s.op_id, r.operation_id, r.operation_ref,
            r.version AS mapped_version, o.ref AS current_operation_ref, t.ref AS task_ref
            FROM "Schedule" s
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.source_key = CAST(s.id AS TEXT)
                AND r.active = 1 AND r.source_table = 'schedule'
            LEFT JOIN WorkbenchTaskRefs t ON t.row_ref = r.ref AND t.plan_ref = ?
            LEFT JOIN BatchOperations bo ON bo.id = s.op_id
            LEFT JOIN WorkbenchPlanSourceRefs o ON o.kind = 'operation' AND o.active = 1
                AND o.source_key = CAST(bo.id AS TEXT)
            WHERE r.kind = 'schedule_row' AND s.id IN ({marks}) AND s.version = ?""", params)

    def _plan_record(self, locator: WorkbenchPlanLocator) -> Dict[str, Any]:
        record = self.source_row("official", str(locator.version))
        if record is None:
            fail_plan_reference("identity_missing")
        if not catalog_identity_matches(record, locator) or not self.history_exists(locator.version):
            fail_plan_reference("plan_binding_invalid")
        return record

    def _resolved_record(self, plan_ref: object) -> Tuple[WorkbenchPlanLocator, Dict[str, Any]]:
        self.read_revision()
        ref = require_plan_ref_format(plan_ref)
        record = self.source_row_by_ref(ref)
        if record is None or record["kind"] != "official":
            fail_plan_reference("reference_not_found")
        locator = validate_plan_locator(WorkbenchPlanLocator(record["version"], record["plan_role"]))
        current = self._plan_record(locator)
        if current["ref"] != ref:
            fail_plan_reference("plan_binding_invalid")
        return locator, record

    def resolve_plan(self, plan_ref: object) -> WorkbenchPlanLocator:
        return self._resolved_record(plan_ref)[0]

    def get_plan_ref(self, locator: Any) -> str:
        self.read_revision()
        normalized = validate_plan_locator(locator)
        return self._plan_record(normalized)["ref"]

    def get_operation_refs(self, ids: Iterable[int]) -> Dict[int, str]:
        self.read_revision()
        values = list(ids)
        if any(not is_exact_positive_int(key) for key in values):
            fail_plan_reference("task_binding_invalid")
        keys = list(dict.fromkeys(values))
        captured: Dict[int, Optional[str]] = {}
        for start in range(0, len(keys), 400):
            chunk = keys[start:start + 400]
            rows = self.operation_ref_rows(chunk)
            captured.update(dict.fromkeys(chunk))
            captured.update((row["id"], row["ref"]) for row in rows)
        output = {key: ref for key in keys for ref in (captured[key],) if ref is not None}
        if len(output) != len(keys):
            fail_plan_reference("identity_missing")
        return output

    def get_task_refs(self, plan_ref: str, rows: Iterable[Tuple[Any, Any, Any]]) -> Dict[int, str]:
        locator, record = self._resolved_record(plan_ref)
        expected = requested_task_ids(rows, locator.version)
        ids = list(expected)
        captured: Dict[int, List[Dict[str, Any]]] = {key: [] for key in ids}
        for start in range(0, len(ids), 400):
            chunk = ids[start:start + 400]
            for row in self.task_ref_rows(record, chunk):
                captured[row["id"]].append(row)
        return extract_task_refs(ids, expected, locator.version, captured)
