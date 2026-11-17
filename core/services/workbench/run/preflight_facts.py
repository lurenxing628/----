"""Raw SQLite facts and complete content bound to an in-process read snapshot."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.execution.ledger_reader import ExecutionLedgerReadScope
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_capture
from core.services.workbench.facts.history_documents import HistoryDocuments
from core.services.workbench.facts.preflight_checks import PreflightChecks
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.source_revisions import PREFLIGHT_SOURCE_KEYS, read_source_revisions
from core.services.workbench.facts.zero_duration import schedule_row_point_evidence

if TYPE_CHECKING:
    from core.errors import ValidationError
    from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot


def _official_point_work_for_rows(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        witness = schedule_row_point_evidence(row)
        if witness is not None:
            result[row["op_id"]] = {"witness": witness}
    return result


class PreflightFacts:
    config_snapshot: Optional["ScheduleConfigSnapshot"]
    config_error: Optional["ValidationError"]

    def __init__(self, conn, *, ledger: ExecutionLedgerReadScope, capture=None):
        self.conn = conn
        self.ledger: ExecutionLedgerReadScope = ledger
        self.capture: Any = capture if capture is not None else ProductionFactsCapture(conn)
        self._fingerprint: Optional[str] = None
        self._tables: Any = None
        self._refs: Any = None
        self._operation_refs: Any = None
        self.execution_projections = {}
        self.resource_execution = {}
        self.external_groups = {}
        self._checks = None
        self._calendars: dict = {}
        self._official_sources: Dict[Any, Any] = {}
        self._configuration_ready = False
        self.config_snapshot, self.config_error = None, None

    @classmethod
    @contextmanager
    def open(cls, conn, *, capture=None) -> Iterator["PreflightFacts"]:
        with candidate_read_snapshot(conn), ledger_read_snapshot(conn) as ledger:
            yield cls(conn, ledger=ledger, capture=capture)

    def fingerprint(self) -> str:
        if self._fingerprint is None:
            self._fingerprint = content_text(
                ["preflight-v2", read_source_revisions(self.conn, PREFLIGHT_SOURCE_KEYS)]
            )
        return self._fingerprint

    def _ensure_tables(self):
        if self._tables is None:
            tables = self.capture.repo.preflight_tables(self.capture)
            self._tables = tables
            self._refs = {
                (row["kind"], row["entity_key"]): row["ref"]
                for row in tables["WorkbenchEntityRefs"]
                if row["active"]
            }
            self._operation_refs = {
                int(row["source_key"]): row["ref"]
                for row in tables["WorkbenchPlanSourceRefs"]
                if row["kind"] == "operation" and row["active"]
            }

    @property
    def tables(self):
        self._ensure_tables()
        return self._tables

    @property
    def refs(self):
        self._ensure_tables()
        return self._refs

    @property
    def operation_refs(self):
        self._ensure_tables()
        return self._operation_refs

    def selected(self, refs):
        identities = {ref: key for (kind, key), ref in self.refs.items() if kind == "batch"}
        batches = {row["batch_id"]: row for row in self.tables["Batches"]}
        result = []
        for ref in refs:
            key = identities.get(ref)
            if key is None:
                raise WorkbenchCommandRejected("entity_not_found", "选中批次已失效，请刷新列表后重新选择。", 404)
            if key not in batches:
                raise WorkbenchCommandRejected("storage_failure", "批次编号和原记录对不上，检查没有继续。请刷新重试；仍不行请联系维护人员。", 500)
            result.append({**batches[key], "ref": ref})
        return result

    def operation_ref(self, op):
        ref = self.operation_refs.get(op["id"])
        if ref is None:
            raise WorkbenchCommandRejected("storage_failure", "工序编号缺失，请联系维护人员。", 500)
        return ref

    def latest_plan_rows(self, version):
        return self.capture.latest_plan_rows(version)

    def checks(self):
        if self._checks is None:
            self._checks = PreflightChecks(self.tables)
        return self._checks

    def calendar(self, operator_ids=None):
        scoped = None if operator_ids is None else frozenset(item for item in operator_ids if item is not None)
        engine = self._calendars.get(scoped)
        if engine is None:
            if scoped is not None:
                if None in self._calendars:
                    return self._calendars[None]
                for existing_scope, existing_engine in self._calendars.items():
                    if existing_scope is not None and scoped <= existing_scope:
                        return existing_engine
            inputs = calendar_inputs_from_capture(self.capture, operator_ids=scoped)
            engine = self._calendars[scoped] = CalendarEngine(inputs)
        return engine

    def configuration(self):
        if not self._configuration_ready:
            from core.errors import ValidationError
            from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot

            try:
                self.config_snapshot = build_schedule_config_snapshot(rows=self.tables["ScheduleConfig"])
            except ValidationError as exc:
                self.config_error = exc
            self._configuration_ready = True
        if self.config_error is not None:
            raise self.config_error.with_traceback(None)
        return self.config_snapshot

    def official_source(self, version):
        """One saved-source preparation over ScheduleHistory and Schedule."""
        if version not in self._official_sources:
            history = next(
                (row for row in self.capture.table("ScheduleHistory") if row["version"] == version),
                None,
            )
            if history is None:
                self._official_sources[version] = None
            else:
                version_rows = [row for row in self.tables["Schedule"] if row["version"] == version]
                self._official_sources[version] = {
                    "documents": HistoryDocuments(history),
                    "point_work": lambda rows=version_rows: _official_point_work_for_rows(rows),
                }
        return self._official_sources[version]

    def public_issue(self, item, op):
        """预检原因只带永久编号：内部工序 id 换成工序、批次编号，页面据此标出是哪批哪道。"""
        result = {key: value for key in item if key != "op_id" for value in (item[key],)}
        result.update(
            operation_ref=self.operation_ref(op),
            batch_ref=self.refs.get(("batch", op["batch_id"])),
            batch_id=op["batch_id"],
        )
        return result
