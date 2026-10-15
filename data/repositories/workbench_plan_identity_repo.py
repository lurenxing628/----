"""SELECT-only permanent refs. Caller owns the connection and read snapshot.

These locators identify stored objects, not complete/executable plans. Continue
using the existing plan catalog/identity service for completeness and capability.
No missing mapping is repaired, no stale ref is rebound, and no latest fallback
exists. Bulk methods are all-or-error, with bounded SQL parameter chunks.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, List, Mapping, NoReturn, Optional, Tuple

from core.infrastructure.read_evidence import read_evidence_scope
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.schedule_plan_role import VALID_PLAN_ROLES, plan_role_order_sql
from core.models.workbench_plan_reference import (
    WorkbenchPlanCatalogReference,
    WorkbenchPlanLocator,
    WorkbenchPlanReferenceError,
    WorkbenchPlanReferenceIssue,
)

from .base_repo import BaseRepository

_REF_PATTERN = re.compile(r"[0-9a-f]{48}\Z")
_ROW_SOURCES = {"schedule": ("Schedule", "schedule_row"),
                "candidate_rows": ("ScheduleCandidateRows", "candidate_row"),
                "adjustment_scenario_rows": ("ScheduleAdjustmentScenarioRow", "scenario_row")}


def _fail(code: str) -> NoReturn:
    messages = {
        "reference_not_found": "所选计划引用不存在或已失效。",
        "identity_missing": "永久身份缺失，不能读取或自动补建。",
        "plan_binding_invalid": "计划身份绑定不完整或已经改变。",
        "task_binding_invalid": "任务不属于所选计划或原工序实例已经改变。",
    }
    raise WorkbenchPlanReferenceError(code, messages[code])


def _positive_int(value: Any) -> bool:
    return type(value) is int and 0 < value <= (1 << 63) - 1


def _catalog_failure(code: str, message: str, plan_ref: Optional[str] = None) -> WorkbenchPlanCatalogReference:
    return WorkbenchPlanCatalogReference(plan_ref, False, (WorkbenchPlanReferenceIssue(code, message),))


def _catalog_identity_matches(record, locator, expected) -> bool:
    return (isinstance(record["ref"], str) and _REF_PATTERN.fullmatch(record["ref"]) is not None
            and (record["version"], record["plan_role"]) == (locator.version, locator.plan_role)
            and all(record[column] == value for column, value in expected.items()))


def _requested_task_ids(rows: Iterable[Mapping[str, Any]], target_version: int) -> Dict[int, int]:
    expected = {}
    for row in rows:
        try:
            row_id, op_id, version = row["schedule_id"], row["op_id"], row["version"]
        except (KeyError, TypeError):
            _fail("task_binding_invalid")
        if not all(_positive_int(value) for value in (row_id, op_id, version)) or version != target_version:
            _fail("task_binding_invalid")
        if row_id in expected and expected[row_id] != op_id:
            _fail("task_binding_invalid")
        expected[row_id] = op_id
    return expected


def _locator(value) -> WorkbenchPlanLocator:
    version, role, scenario = value.version, value.plan_role, value.scenario_id
    if not _positive_int(version) or role not in VALID_PLAN_ROLES:
        _fail("plan_binding_invalid")
    if scenario is not None and (not isinstance(scenario, str) or not scenario or "\x00" in scenario):
        _fail("plan_binding_invalid")
    return WorkbenchPlanLocator(version, role, scenario)


class WorkbenchPlanIdentityRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._checked_schema_version = None
        self._binding_facts = None
        self._history_reader: Optional[Callable[[int], List[Dict[str, Any]]]] = None
        self._scenario_reader: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None

    @contextmanager
    def read_bindings(self):
        """Own binding facts for this read-only transaction; nested reads reuse them."""
        if not self.conn.in_transaction:
            raise RuntimeError("Plan binding facts require the caller's read transaction")
        previous = self._binding_facts
        if previous is not None:
            self._check_schema()
            yield
            return
        with read_evidence_scope(self.conn):
            facts = {"changes": self.conn.total_changes, "history": {}, "roles": {}, "role_rows": {}, "sources": {},
                     "resolved": {}, "operations": {}, "tasks": {}}
            self._binding_facts = facts
            try:
                self._check_schema()
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
        present = (bool(self._history_reader(version)) if self._history_reader is not None else
                   self.fetchone("SELECT 1 FROM ScheduleHistory WHERE version = ? LIMIT 1", (version,)) is not None)
        if cached is not None:
            cached[version] = present
        return present

    def _check_schema(self) -> int:
        if self._binding_facts is not None:
            self._binding_cache("history")
            if "revision" in self._binding_facts:
                return self._binding_facts["revision"]
        version = self.fetchvalue("SELECT schema_version FROM pragma_schema_version")
        if version != self._checked_schema_version:
            issues = workbench_plan_identity_contract_issues(self.conn)
            if issues:
                raise RuntimeError("Workbench plan identity schema unavailable: " + "; ".join(issues))
            self._checked_schema_version = version
        revision = self.fetchvalue("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton = 1")
        if not _positive_int(revision):
            _fail("identity_missing")
        if self._binding_facts is not None:
            self._binding_facts["revision"] = revision
        return revision

    def read_revision(self) -> int:
        """Clock for the eight identity source tables only, NOT all workspace facts."""
        return self._check_schema()

    def _source(self, kind: str, key: str):
        cached = self._binding_cache("sources")
        if cached is not None and (kind, key) in cached:
            return cached[kind, key]
        row = self.fetchone("SELECT * FROM WorkbenchPlanSourceRefs WHERE kind = ? "
                            "AND source_key = ? AND active = 1", (kind, key))
        if cached is not None:
            cached[kind, key] = row
        return row

    def _roles(self, version: int) -> Dict[str, Dict[str, Any]]:
        cached = self._binding_cache("roles")
        if cached is not None and version in cached:
            return cached[version]
        rows = self._role_rows(version)
        roles = {row["role"]: row for row in rows}
        if rows and "adopted" not in roles:
            _fail("plan_binding_invalid")
        for row in rows:
            self._validate_role_binding(row, roles)
        if cached is not None:
            cached[version] = roles
        return roles

    def _role_rows(self, version):
        cached = self._binding_cache("role_rows")
        if cached is not None and version in cached:
            return cached[version]
        rows = self.fetchall(f"""SELECT s.*, c.id AS resolved_id, c.candidate_key,
            c.candidate_label,c.candidate_kind,c.status AS candidate_status,c.detail_saved,
            c.summary_json AS candidate_summary_json,
            CAST(s.id AS TEXT) AS selection_identity_key,CAST(s.candidate_id AS TEXT) AS selection_owner_key,
            m.ref AS selection_ref, m.version AS mapped_version, m.plan_role AS mapped_role,
            m.source_table AS mapped_source, m.owner_key AS mapped_owner,
            m.parent_ref, p.ref AS candidate_ref
            FROM ScheduleCandidateSelection s
            LEFT JOIN ScheduleCandidate c ON c.id = s.candidate_id AND c.version = s.version
            LEFT JOIN WorkbenchPlanSourceRefs m ON m.kind = 'selection'
                AND m.source_key = CAST(s.id AS TEXT) AND m.active = 1
            LEFT JOIN WorkbenchPlanSourceRefs p ON p.kind = 'candidate'
                AND p.source_key = CAST(c.id AS TEXT) AND p.version = c.version AND p.active = 1
            WHERE s.version = ? ORDER BY {plan_role_order_sql("s.role")}""", (version,))
        if cached is not None:
            cached[version] = rows
        return rows

    def read_role_options(self, version):
        fields = ("role", "source_table", "candidate_key", "candidate_label", "candidate_kind", "candidate_status", "detail_saved")
        return [{**{key: row[key] for key in fields}, "selection_candidate_id": row["candidate_id"],
                 "resolved_candidate_id": row["resolved_id"], "candidate_id": row["resolved_id"]}
                for row in self._role_rows(version)]

    @staticmethod
    def _validate_role_binding(row, roles) -> None:
        if row["selection_ref"] is None or row["candidate_ref"] is None:
            _fail("identity_missing" if row["resolved_id"] is not None else "plan_binding_invalid")
        expected = (row["version"], row["role"], row["source_table"], str(row["candidate_id"]), row["candidate_ref"])
        actual = (row["mapped_version"], row["mapped_role"], row["mapped_source"], row["mapped_owner"], row["parent_ref"])
        if actual != expected or row["role"] not in VALID_PLAN_ROLES:
            _fail("plan_binding_invalid")
        if row["source_table"] not in ("schedule", "candidate_rows"):
            _fail("plan_binding_invalid")
        if row["role"] == "adopted" and row["source_table"] != "schedule":
            _fail("plan_binding_invalid")
        if row["source_table"] == "schedule" and row["candidate_id"] != roles["adopted"]["candidate_id"]:
            _fail("plan_binding_invalid")

    def _plan_record(self, locator: WorkbenchPlanLocator, *, history_proven=False, roles=None) -> Dict[str, Any]:
        if locator.scenario_id is not None:
            record = self._source("scenario", locator.scenario_id)
        elif locator.plan_role == "adopted":
            record = self._source("official", str(locator.version))
        else:
            records = self.fetchall("SELECT * FROM WorkbenchPlanSourceRefs WHERE kind = 'selection' "
                                    "AND version = ? AND plan_role = ? AND active = 1 LIMIT 2",
                                    (locator.version, locator.plan_role))
            if len(records) > 1:
                _fail("plan_binding_invalid")
            record = records[0] if records else None
        if record is None:
            _fail("identity_missing")
        self._validate_record(record, locator, history_proven=history_proven, roles=roles)
        return record

    def _validate_record(self, record, locator: WorkbenchPlanLocator, *, history_proven=False, roles=None) -> None:
        if (record["version"], record["plan_role"]) != (locator.version, locator.plan_role):
            _fail("plan_binding_invalid")
        if not history_proven and not self._history_exists(locator.version):
            _fail("plan_binding_invalid")
        roles = self._roles(locator.version) if roles is None else roles
        if locator.scenario_id is not None:
            self._validate_scenario(record, locator, roles)
        elif locator.plan_role != "adopted":
            role = roles.get(locator.plan_role)
            if role is None or role["selection_ref"] != record["ref"]:
                _fail("plan_binding_invalid")
        elif record["kind"] != "official" or record["source_table"] != "schedule":
            _fail("plan_binding_invalid")

    def _validate_scenario(self, record, locator, roles) -> None:
        scenario = (self._scenario_reader(locator.scenario_id) if self._scenario_reader is not None else
                    self.fetchone("SELECT * FROM ScheduleAdjustmentScenario WHERE scenario_id = ?", (locator.scenario_id,)))
        if scenario is None or (scenario["base_version"], scenario["base_plan_role"]) != (locator.version, locator.plan_role):
            _fail("plan_binding_invalid")
        base = self._plan_record(WorkbenchPlanLocator(locator.version, locator.plan_role),
                                 history_proven=True, roles=roles)
        role = roles.get(locator.plan_role)
        expected = ("schedule", None, None) if role is None else (
            role["source_table"], role["candidate_id"], role["candidate_key"])
        actual = (scenario["base_source_table"], scenario["base_candidate_id"], scenario["base_candidate_key"])
        if record["parent_ref"] != base["ref"] or actual != expected:
            _fail("plan_binding_invalid")
        if record["source_table"] != "adjustment_scenario_rows":
            _fail("plan_binding_invalid")

    def _resolved_record(self, plan_ref: str):
        self._check_schema()
        if not isinstance(plan_ref, str) or _REF_PATTERN.fullmatch(plan_ref) is None:
            _fail("reference_not_found")
        cached = self._binding_cache("resolved")
        if cached is not None and plan_ref in cached:
            return cached[plan_ref]
        record = self.fetchone("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref = ? AND active = 1", (plan_ref,))
        if record is None or record["kind"] not in ("official", "selection", "scenario"):
            _fail("reference_not_found")
        if record["kind"] == "selection" and record["plan_role"] == "adopted":
            _fail("reference_not_found")
        sources = self._binding_cache("sources")
        if sources is not None:
            sources[record["kind"], record["source_key"]] = record
        locator = _locator(WorkbenchPlanLocator(record["version"], record["plan_role"],
                            record["source_key"] if record["kind"] == "scenario" else None))
        current = self._plan_record(locator)
        if current["ref"] != plan_ref:
            _fail("plan_binding_invalid")
        if cached is not None:
            cached[plan_ref] = locator, record
        return locator, record

    def resolve_plan(self, plan_ref: str) -> WorkbenchPlanLocator:
        return self._resolved_record(plan_ref)[0]

    def get_plan_ref(self, locator) -> str:
        """Also accepts the existing private PlanCatalogLocator's three fields."""
        self._check_schema()
        locator = _locator(locator)
        record = self._plan_record(locator)
        cached = self._binding_cache("resolved")
        if cached is not None:
            cached[record["ref"]] = locator, record
        return str(record["ref"])

    def _catalog_source(self, locator: WorkbenchPlanLocator) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        if locator.scenario_id is not None:
            source = (self._scenario_reader(locator.scenario_id) if self._scenario_reader is not None else
                      self.fetchone("SELECT scenario_id, base_version, base_plan_role, source_draft_id "
                                     "FROM ScheduleAdjustmentScenario WHERE scenario_id = ?", (locator.scenario_id,)))
            if source is None:
                return None
            return "scenario", str(source["scenario_id"]), {
                "version": source["base_version"], "plan_role": source["base_plan_role"],
                "source_table": "adjustment_scenario_rows", "alternate_key": source["source_draft_id"],
            }
        if locator.plan_role == "adopted":
            if self._history_reader is None:
                source = self.fetchone("SELECT version, CAST(version AS TEXT) AS identity_key FROM ScheduleHistory "
                                        "WHERE version = ? LIMIT 1", (locator.version,))
            else:
                rows = self._history_reader(locator.version)
                source = {"version": rows[0]["version"], "identity_key": str(rows[0]["version"])} if rows else None
            if self._binding_facts is not None:
                self._binding_facts["history"][locator.version] = source is not None
            if source is None:
                return None
            return "official", source["identity_key"], {
                "version": source["version"], "plan_role": "adopted", "source_table": "schedule",
            }
        if self._binding_facts is None:
            source = self.fetchone("SELECT id, version, role, CAST(candidate_id AS TEXT) AS owner_key, source_table FROM ScheduleCandidateSelection "
                                    "WHERE version = ? AND role = ?", (locator.version, locator.plan_role))
            if source is None:
                return None
            key = str(source["id"])
        else:
            row = next((row for row in self._role_rows(locator.version) if row["role"] == locator.plan_role), None)
            if row is None:
                return None
            source = dict(row, owner_key=row["selection_owner_key"])
            key = row["selection_identity_key"]
        return "selection", key, {
            "version": source["version"], "plan_role": source["role"],
            "source_table": source["source_table"], "owner_key": source["owner_key"],
        }

    def get_catalog_reference(self, locator) -> WorkbenchPlanCatalogReference:
        """Retain a proven object's ref for a disabled catalog entry, never permission.

        Only expected per-plan binding failures become issues. Missing schema,
        clock and storage errors still raise. Detail/task APIs remain strict.
        """
        self._check_schema()
        invalid_context = None
        try:
            normalized = _locator(locator)
        except WorkbenchPlanReferenceError as exc:
            scenario = locator.scenario_id
            if scenario is not None and (not isinstance(scenario, str) or not scenario or "\x00" in scenario):
                return _catalog_failure("identity_invalid", str(exc))
            normalized, invalid_context = locator, str(exc)
        source = self._catalog_source(normalized)
        if source is None:
            return _catalog_failure("source_missing", "计划源对象已不存在。")
        kind, key, expected = source
        record = self._source(kind, key)
        if record is None:
            return _catalog_failure("identity_missing", "计划的永久身份缺失，不能自动补建。")
        if not _catalog_identity_matches(record, normalized, expected):
            return _catalog_failure("identity_invalid", "永久身份与当前计划源对象不一致。")
        plan_ref = record["ref"]
        if invalid_context is not None:
            return _catalog_failure("plan_binding_invalid", invalid_context, plan_ref)
        history_proven = kind == "official"
        if not history_proven and not self._history_exists(normalized.version):
            return _catalog_failure("history_missing", "计划的基础排产历史不存在。", plan_ref)
        try:
            self._validate_record(record, normalized, history_proven=True)
        except WorkbenchPlanReferenceError as exc:
            return _catalog_failure("plan_binding_invalid", str(exc), plan_ref)
        cached = self._binding_cache("resolved")
        if cached is not None:
            cached[plan_ref] = normalized, record
        return WorkbenchPlanCatalogReference(plan_ref, True)

    def get_operation_refs(self, ids: Iterable[int]) -> Dict[int, str]:
        self._check_schema()
        values = list(ids)
        if any(not _positive_int(key) for key in values):
            _fail("task_binding_invalid")
        keys = list(dict.fromkeys(values))
        cached = self._binding_cache("operations")
        captured = cached if cached is not None else {}
        missing = [key for key in keys if key not in captured]
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            # Keep the bounded primary-key set outermost. SQLite 3.35 can otherwise
            # scan every active ref once per chunk through the CAST expression.
            # "+bo.id" keeps the CAST off idx_wb_lineage_operation_id_text: SQLite
            # 3.46 probes that index with the raw integer for a one-key chunk and
            # returns no rows.
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
        table, kind = _ROW_SOURCES[record["source_table"]]
        params = [record["ref"], kind] + ids
        where = "s.version = ?"
        if kind == "scenario_row":
            where = "s.scenario_id = ? AND r.parent_ref = ?"
            params += [record["source_key"], record["ref"]]
        else:
            params.append(record["version"])
            if kind == "candidate_row":
                where += " AND s.candidate_id = ? AND r.parent_ref = ?"
                params += [record["owner_key"], record["parent_ref"]]
        marks = ",".join("?" for _ in ids)
        return self.fetchall(f"""SELECT s.id, s.op_id, r.operation_id, r.operation_ref,
            r.version AS mapped_version, o.ref AS current_operation_ref, t.ref AS task_ref
            FROM "{table}" s
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.source_key = CAST(s.id AS TEXT)
                AND r.active = 1 AND r.source_table = '{record['source_table']}'
            LEFT JOIN WorkbenchTaskRefs t ON t.row_ref = r.ref AND t.plan_ref = ?
            LEFT JOIN BatchOperations bo ON bo.id = s.op_id
            LEFT JOIN WorkbenchPlanSourceRefs o ON o.kind = 'operation' AND o.active = 1
                AND o.source_key = CAST(bo.id AS TEXT)
            WHERE r.kind = ? AND s.id IN ({marks}) AND {where}""", params)

    def get_task_refs(self, plan_ref: str, rows: Iterable[Mapping[str, Any]]) -> Dict[int, str]:
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
                if record["kind"] != "scenario" and row["mapped_version"] != locator.version:
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
