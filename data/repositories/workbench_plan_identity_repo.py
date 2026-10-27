"""SELECT-only permanent refs. Caller owns the connection and read snapshot.

These locators identify stored objects, not complete/executable plans. Continue
using the existing plan catalog/identity service for completeness and capability.
No missing mapping is repaired, no stale ref is rebound, and no latest fallback
exists. Bulk methods are all-or-error, with bounded SQL parameter chunks.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, List, NoReturn, Optional, Tuple

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.read_evidence import read_evidence_scope
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.schedule_plan_role import ROLE_ADOPTED, VALID_PLAN_ROLES
from core.models.workbench_plan_reference import (
    WorkbenchPlanCatalogReference,
    WorkbenchPlanLocator,
    WorkbenchPlanReferenceError,
    WorkbenchPlanReferenceIssue,
)
from core.shared.strict_parse import is_exact_positive_int

from .base_repo import BaseRepository

_REF_PATTERN = re.compile(r"[0-9a-f]{48}\Z")


def _fail(code: str) -> NoReturn:
    messages = {
        "reference_not_found": "所选计划引用不存在或已失效。",
        "identity_missing": "永久身份缺失，不能读取或自动补建。",
        "plan_binding_invalid": "计划身份绑定不完整或已经改变。",
        "task_binding_invalid": "任务不属于所选计划或原工序实例已经改变。",
    }
    raise WorkbenchPlanReferenceError(code, messages[code])


def _catalog_failure(code: str, message: str, plan_ref: Optional[str] = None) -> WorkbenchPlanCatalogReference:
    return WorkbenchPlanCatalogReference(plan_ref, False, (WorkbenchPlanReferenceIssue(code, message),))


def _catalog_identity_matches(record, locator) -> bool:
    return (isinstance(record["ref"], str) and _REF_PATTERN.fullmatch(record["ref"]) is not None
            and (record["version"], record["plan_role"]) == (locator.version, locator.plan_role)
            and record["kind"] == "official" and record["source_table"] == "schedule")


def _requested_task_ids(rows: Iterable[Tuple[Any, Any, Any]], target_version: int) -> Dict[int, int]:
    expected = {}
    for row_id, op_id, version in rows:
        if not all(is_exact_positive_int(value) for value in (row_id, op_id, version)) or version != target_version:
            _fail("task_binding_invalid")
        if row_id in expected and expected[row_id] != op_id:
            _fail("task_binding_invalid")
        expected[row_id] = op_id
    return expected


def _locator(value) -> WorkbenchPlanLocator:
    version, role = value.version, value.plan_role
    if not is_exact_positive_int(version) or role not in VALID_PLAN_ROLES:
        _fail("plan_binding_invalid")
    return WorkbenchPlanLocator(version, role)


class WorkbenchPlanIdentityRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._binding_facts = None

    @contextmanager
    def read_bindings(self, *, history_reader: Optional[Callable[[int], List[Dict[str, Any]]]] = None):
        """Own binding facts for this read-only transaction; nested reads reuse them.

        The reader serves plan history rows the caller already reads in this
        transaction; without it those rows come from SQL. A nested scope that brings its
        own reader uses it until it exits.
        """
        if not self.conn.in_transaction:
            raise RuntimeError("Plan binding facts require the caller's read transaction")
        previous = self._binding_facts
        if previous is not None:
            self.read_revision()
            if history_reader is None:
                yield
                return
            outer = previous["history_reader"]
            previous["history_reader"] = history_reader
            try:
                yield
            finally:
                previous["history_reader"] = outer
            return
        with read_evidence_scope(self.conn):
            facts: Dict[str, Any] = {
                "changes": self.conn.total_changes, "history": {}, "sources": {},
                "resolved": {}, "operations": {}, "tasks": {},
                "history_reader": history_reader}
            self._binding_facts = facts
            try:
                self.read_revision()
                yield
            finally:
                self._binding_facts = previous
                facts.clear()

    def _binding_cache(self, name):
        facts = self._binding_facts
        if facts is None:
            return None
        if not self.conn.in_transaction or self.conn.total_changes != facts["changes"]:
            raise RuntimeError("Plan binding read snapshot changed")
        return facts[name]

    def _history_exists(self, version):
        cached = self._binding_cache("history")
        if cached is not None and version in cached:
            return cached[version]
        history_reader = self._binding_cache("history_reader")
        present = (bool(history_reader(version)) if history_reader is not None else
                   self.fetchone("SELECT 1 FROM ScheduleHistory WHERE version = ? LIMIT 1", (version,)) is not None)
        if cached is not None:
            cached[version] = present
        return present

    def read_revision(self) -> int:
        """Validate the identity schema and return the clock of the identity source tables only.

        NOT a clock of all workspace facts; inside read_bindings the first check is reused.
        """
        if self._binding_facts is not None:
            self._binding_cache("history")
            if "revision" in self._binding_facts:
                return self._binding_facts["revision"]
        issues = schema_contract_memo(self.conn).get_schema(workbench_plan_identity_contract_issues)
        if issues:
            raise RuntimeError("Workbench plan identity schema unavailable: " + "; ".join(issues))
        revision = self.fetchvalue("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton = 1")
        if not is_exact_positive_int(revision):
            _fail("identity_missing")
        if self._binding_facts is not None:
            self._binding_facts["revision"] = revision
        return revision

    def _source(self, kind: str, key: str):
        cached = self._binding_cache("sources")
        if cached is not None and (kind, key) in cached:
            return cached[kind, key]
        row = self.fetchone("SELECT * FROM WorkbenchPlanSourceRefs WHERE kind = ? "
                            "AND source_key = ? AND active = 1", (kind, key))
        if cached is not None:
            cached[kind, key] = row
        return row

    def _plan_record(self, locator: WorkbenchPlanLocator) -> Dict[str, Any]:
        record = self._source("official", str(locator.version))
        if record is None:
            _fail("identity_missing")
        self._validate_record(record, locator)
        return record

    def _validate_record(self, record, locator: WorkbenchPlanLocator) -> None:
        if not _catalog_identity_matches(record, locator):
            _fail("plan_binding_invalid")
        if not self._history_exists(locator.version):
            _fail("plan_binding_invalid")

    def _resolved_record(self, plan_ref: object):
        """Plan refs may come from requests or saved records, so their format is checked here."""
        self.read_revision()
        if not isinstance(plan_ref, str) or _REF_PATTERN.fullmatch(plan_ref) is None:
            _fail("reference_not_found")
        cached = self._binding_cache("resolved")
        if cached is not None and plan_ref in cached:
            return cached[plan_ref]
        record = self.fetchone("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref = ? AND active = 1", (plan_ref,))
        if record is None or record["kind"] != "official":
            _fail("reference_not_found")
        sources = self._binding_cache("sources")
        if sources is not None:
            sources[record["kind"], record["source_key"]] = record
        locator = _locator(WorkbenchPlanLocator(record["version"], record["plan_role"]))
        current = self._plan_record(locator)
        if current["ref"] != plan_ref:
            _fail("plan_binding_invalid")
        if cached is not None:
            cached[plan_ref] = locator, record
        return locator, record

    def resolve_plan(self, plan_ref: object) -> WorkbenchPlanLocator:
        return self._resolved_record(plan_ref)[0]

    def get_plan_ref(self, locator) -> str:
        """Also accepts the existing private PlanCatalogLocator's two fields."""
        self.read_revision()
        locator = _locator(locator)
        record = self._plan_record(locator)
        cached = self._binding_cache("resolved")
        if cached is not None:
            cached[record["ref"]] = locator, record
        return str(record["ref"])

    def _catalog_source(self, locator: WorkbenchPlanLocator) -> Optional[Tuple[str, str]]:
        if locator.plan_role != ROLE_ADOPTED:
            return None
        history_reader = self._binding_cache("history_reader")
        if history_reader is None:
            source = self.fetchone("SELECT version, CAST(version AS TEXT) AS identity_key FROM ScheduleHistory "
                                    "WHERE version = ? LIMIT 1", (locator.version,))
        else:
            rows = history_reader(locator.version)
            source = {"version": rows[0]["version"], "identity_key": str(rows[0]["version"])} if rows else None
        if self._binding_facts is not None:
            self._binding_facts["history"][locator.version] = source is not None
        if source is None:
            return None
        return "official", source["identity_key"]

    def get_catalog_reference(self, locator) -> WorkbenchPlanCatalogReference:
        """Retain a proven object's ref for a disabled catalog entry, never permission.

        Only expected per-plan binding failures become issues. Missing schema,
        clock and storage errors still raise. Detail/task APIs remain strict.
        """
        self.read_revision()
        invalid_context = None
        try:
            normalized = _locator(locator)
        except WorkbenchPlanReferenceError as exc:
            normalized, invalid_context = locator, str(exc)
        source = self._catalog_source(normalized)
        if source is None:
            return _catalog_failure("source_missing", "计划源对象已不存在。")
        kind, key = source
        record = self._source(kind, key)
        if record is None:
            return _catalog_failure("identity_missing", "计划的永久身份缺失，不能自动补建。")
        if not _catalog_identity_matches(record, normalized):
            return _catalog_failure("identity_invalid", "永久身份与当前计划源对象不一致。")
        plan_ref = record["ref"]
        if invalid_context is not None:
            return _catalog_failure("plan_binding_invalid", invalid_context, plan_ref)
        cached = self._binding_cache("resolved")
        if cached is not None:
            cached[plan_ref] = normalized, record
        return WorkbenchPlanCatalogReference(plan_ref, True)

    def get_operation_refs(self, ids: Iterable[int]) -> Dict[int, str]:
        self.read_revision()
        values = list(ids)
        if any(not is_exact_positive_int(key) for key in values):
            _fail("task_binding_invalid")
        keys = list(dict.fromkeys(values))
        cached = self._binding_cache("operations")
        captured = cached if cached is not None else {}
        missing = [key for key in keys if key not in captured]
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT bo.id, m.ref FROM BatchOperations bo "
                                 "CROSS JOIN WorkbenchPlanSourceRefs m ON m.kind = 'operation' AND m.active = 1 "
                                 f"AND m.source_key = CAST(+bo.id AS TEXT) WHERE bo.id IN ({marks})", chunk)
            captured.update(dict.fromkeys(chunk))
            captured.update((row["id"], row["ref"]) for row in rows)
        output = {key: captured[key] for key in keys if captured[key] is not None}
        if len(output) != len(keys):
            _fail("identity_missing")
        return output

    def _task_rows(self, record, ids):
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

    def get_task_refs(self, plan_ref: str, rows: Iterable[Tuple[Any, Any, Any]]) -> Dict[int, str]:
        """Task refs keyed by schedule id; ``rows`` are the arrangements' ``(schedule_id, op_id, version)``."""
        locator, record = self._resolved_record(plan_ref)
        expected = _requested_task_ids(rows, locator.version)
        ids, output = list(expected), {}
        cached = self._binding_cache("tasks")
        captured = cached.setdefault(plan_ref, {}) if cached is not None else {}
        missing = [key for key in ids if key not in captured]
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            actual = self._task_rows(record, chunk)
            for key in chunk:
                captured[key] = []
            for row in actual:
                captured[row["id"]].append(row)
        operation_refs = self._binding_cache("operations")
        for key in ids:
            for row in captured[key]:
                if row["op_id"] != expected[row["id"]] or row["operation_id"] != row["op_id"]:
                    _fail("task_binding_invalid")
                if row["mapped_version"] != locator.version:
                    _fail("task_binding_invalid")
                if not row["operation_ref"] or row["operation_ref"] != row["current_operation_ref"]:
                    _fail("task_binding_invalid")
                if row["task_ref"] is None:
                    _fail("identity_missing")
                output[row["id"]] = row["task_ref"]
                if operation_refs is not None:
                    operation_refs[row["op_id"]] = row["current_operation_ref"]
        if len(output) != len(expected):
            _fail("task_binding_invalid")
        return output
