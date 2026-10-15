"""Raw SQLite facts and complete content bound to an in-process read snapshot."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.production_capture import NON_INPUT_TABLES, ProductionFactsCapture, non_input_row
from data.repositories.workbench_preflight_facts_repo import PREFLIGHT_TABLES, WorkbenchPreflightFactsRepository

if TYPE_CHECKING:
    from core.errors import ValidationError
    from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

TABLES = PREFLIGHT_TABLES


def full_facts_content(conn, capture=None):
    if capture is not None:
        return capture.content()
    with TransactionManager(conn).transaction():
        return ProductionFactsCapture(conn).content()


class PreflightFacts:
    config_snapshot: Optional["ScheduleConfigSnapshot"]
    config_error: Optional["ValidationError"]

    def __init__(self, conn, *, capture=None):
        self.conn = conn
        self.repo = WorkbenchPreflightFactsRepository(conn)
        self._shared_capture = capture
        self.capture = capture
        self.tables = {}
        self.refs = {}
        self.operation_refs = {}

    @contextmanager
    def snapshot(self, *, fingerprint=True):
        with TransactionManager(self.conn).transaction():
            capture = self._shared_capture if self._shared_capture is not None else ProductionFactsCapture(self.conn)
            self.bind_capture(capture)
            yield full_facts_content(self.conn, self.capture) if fingerprint else ""

    def bind_capture(self, capture):
        self.capture = capture
        self.tables = self.repo.preflight_tables(capture=capture)
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

    def schedule_through(self, version):
        """与排产输入同口径：version 及以前的正式安排，按 version,id 排序，同一工序后者为准。"""
        return sorted((row for row in self.tables["Schedule"] if row["version"] <= version), key=lambda row: (row["version"], row["id"]))

    def public_issue(self, item, op):
        """预检原因只带永久编号：内部工序 id 换成工序、批次编号，页面据此标出是哪批哪道。"""
        result = {key: value for key, value in item.items() if key != "op_id"}
        result.update(operation_ref=self.operation_ref(op), batch_ref=self.refs.get(("batch", op["batch_id"])), batch_id=op["batch_id"])
        return result
