"""Raw SQLite facts and complete content bound to an in-process read snapshot."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot

if TYPE_CHECKING:
    from core.errors import ValidationError
    from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot


class PreflightFacts:
    config_snapshot: Optional["ScheduleConfigSnapshot"]
    config_error: Optional["ValidationError"]

    def __init__(self, conn, *, capture=None):
        self.conn = conn
        self._shared_capture = capture
        self.capture: Any = capture
        self.execution_service = None
        self.tables = {}
        self.refs = {}
        self.operation_refs = {}
        self.execution_projections = {}
        self.resource_execution = {}
        self.external_groups = {}
        self._checks = None
        self._calendar = None
        self._official_sources, self._source_resolver = {}, None
        self._configuration_ready = False
        self.config_snapshot, self.config_error = None, None
        self._snapshot_depth = 0

    @contextmanager
    def snapshot(self, *, fingerprint=True):
        if self._snapshot_depth > 0:
            yield self.capture.content() if fingerprint else ""
            return
        with candidate_read_snapshot(self.conn):
            capture = self._shared_capture if self._shared_capture is not None else ProductionFactsCapture(self.conn)
            self.bind_capture(capture)
            self._snapshot_depth += 1
            try:
                with self.execution_snapshot():
                    yield self.capture.content() if fingerprint else ""
            finally:
                self._snapshot_depth -= 1

    @contextmanager
    def execution_snapshot(self):
        from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot

        if schema_contract_memo(self.conn).get_schema(execution_ledger_contract_issues):
            yield None
            return
        with ledger_read_snapshot(self.conn, ledger=self.execution_service) as ledger:
            self.execution_service = ledger
            self.capture.execution_service = ledger
            yield ledger

    def bind_capture(self, capture):
        if self.capture is capture and self.tables:
            return
        self.execution_projections, self.resource_execution, self.external_groups = {}, {}, {}
        self._checks = None
        self._calendar = None
        self._official_sources, self._source_resolver = {}, None
        self._configuration_ready = False
        self.config_snapshot, self.config_error = None, None
        self.capture = capture
        self.execution_service = capture.execution_service
        self.tables = capture.repo.preflight_tables(capture)
        self.refs = {(row["kind"], row["entity_key"]): row["ref"]
                     for row in self.tables["WorkbenchEntityRefs"] if row["active"]}
        self.operation_refs = {int(row["source_key"]): row["ref"] for row in self.tables["WorkbenchPlanSourceRefs"]
                               if row["kind"] == "operation" and row["active"]}

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
            from core.services.workbench.facts.preflight_checks import PreflightChecks

            self._checks = PreflightChecks(self.tables)
        return self._checks

    def calendar(self):
        if self._calendar is None:
            from core.services.scheduler.calendar.service import CalendarService

            self._calendar = CalendarService(self.conn, capture=self.capture)
        return self._calendar

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
        """One saved-source preparation serves retained effort and point evidence."""
        if version not in self._official_sources:
            histories = [row for row in self.capture.table("ScheduleHistory") if row["version"] == version]
            refs = [row["ref"] for row in self.tables["WorkbenchPlanSourceRefs"]
                    if row["kind"] == "official" and row["active"] == 1 and row["version"] == version]
            if len(histories) != 1 or len(refs) != 1:
                self._official_sources[version] = None
            else:
                if self._source_resolver is None:
                    from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver

                    self._source_resolver = decision_baseline_source_resolver(self.conn)
                self._official_sources[version] = self._source_resolver(
                    plan_ref=refs[0], version=version, history=histories[0])
        return self._official_sources[version]

    def public_issue(self, item, op):
        """预检原因只带永久编号：内部工序 id 换成工序、批次编号，页面据此标出是哪批哪道。"""
        result = {key: value for key, value in item.items() if key != "op_id"}
        result.update(operation_ref=self.operation_ref(op), batch_ref=self.refs.get(("batch", op["batch_id"])), batch_id=op["batch_id"])
        return result
