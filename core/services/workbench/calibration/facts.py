"""One caller-owned SQLite snapshot and shared collection/point calibration facts.

The query repository returns bounded rows only; schema readiness, missing identities
and size limits are ruled on here before anything is projected.
"""

from datetime import datetime
from typing import ContextManager, Optional

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.workbench_calibration import MAX_TEMPLATES, CalibrationTemplate
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_OPERATIONS
from core.services.execution.ledger_reader import ExecutionLedgerReadScope, project_loaded_facts
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.source_revisions import CALIBRATION_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository

from .template_lineage_calibration import (
    project_single_template_calibration,
    project_state_calibration,
)


def to_calibration_template(row) -> CalibrationTemplate:
    """row INNER JOINs an active template with its active template and part identities (FK and identity
    triggers); both refs are WorkbenchEntityRefs.ref, whose CHECK already pins the form."""
    source = row["source"] if row["source"] in OPERATION_SOURCES else "unknown"
    return CalibrationTemplate(
        row["operation_ref"],
        row["revision"],
        row["part_ref"],
        row["part_no"],
        row["part_name"],
        row["seq"],
        row["op_type_name"],
        source,
        row["unit_hours"],
    )


def read_templates(repo, query, *, part_identity):
    part_no = part_identity["entity_key"] if part_identity is not None else None
    rows = repo.template_rows(
        part_no,
        MAX_TEMPLATES,
        source=query.source,
        search=query.query,
    )
    if len(rows) > MAX_TEMPLATES:
        raise WorkbenchCommandRejected("query_too_large", "模板范围超过10000道，请按零件缩小范围；未截断数据。", 413)
    return [to_calibration_template(row) for row in rows]


def read_single_template_row(
    repo,
    template_ref: str,
    query,
    *,
    part_identity,
) -> Optional[CalibrationTemplate]:
    part_no = part_identity["entity_key"] if part_identity is not None else None
    row = repo.template_row(
        template_ref,
        part_no=part_no,
        source=query.source,
        search=query.query,
    )
    if row is None:
        return None
    return to_calibration_template(row)


def _check_instance_rows(rows):
    if len(rows) > MAX_WINDOW_OPERATIONS:
        raise WorkbenchCommandRejected(
            "query_too_large", f"待核对执行工序超过{MAX_WINDOW_OPERATIONS}道，请缩小零件范围；未截断样本。", 413
        )
    if any(row["operation_ref"] is None for row in rows):
        raise WorkbenchCommandRejected("calibration_source_unavailable", "执行实例永久身份缺失，不能按批次号或工序号补配。")
    return rows


def read_candidate_instances(repo, part_numbers, template_refs):
    """Same-part records are audit candidates only, NOT template sample matches."""
    return _check_instance_rows(repo.candidate_instance_rows(part_numbers, template_refs, MAX_WINDOW_OPERATIONS))


def read_template_candidate_instances(repo, part_no: str, template_ref: str):
    """Point lookup of candidate instances for one template and same-part unbound rows."""
    return _check_instance_rows(repo.template_candidate_instance_rows(part_no, template_ref, MAX_WINDOW_OPERATIONS))


class CalibrationFacts:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchCalibrationQueryRepository(conn)
        self.ledger = ExecutionLedgerService(conn)

    def read_snapshot(self) -> ContextManager[ExecutionLedgerReadScope]:
        return self.ledger.read_snapshot()

    def _resolve_part_and_snapshot(self, ledger_scope: ExecutionLedgerReadScope, query, *, bind_snapshot):
        part_identity = None
        if query.part_ref is not None:
            part_identity = self.repo.part_identity(query.part_ref)
            if part_identity is None:
                raise WorkbenchCommandRejected("entity_not_found", "所选零件已失效，请重新选择。", 404)
        snapshot = None
        if bind_snapshot is not None:
            content = {
                "revisions": read_source_revisions(self.conn, CALIBRATION_SOURCE_KEYS),
                "ledger_revision": self.ledger.revision_clock(ledger_scope),
                "scope": query.scope(),
            }
            snapshot = bind_snapshot(content)
        return part_identity, snapshot

    def read(self, ledger_scope: ExecutionLedgerReadScope, query, *, as_of: datetime, bind_snapshot=None):
        part_identity, snapshot = self._resolve_part_and_snapshot(
            ledger_scope, query, bind_snapshot=bind_snapshot
        )
        templates = read_templates(self.repo, query, part_identity=part_identity)
        instances = read_candidate_instances(
            self.repo,
            [row.part_no for row in templates],
            [row.operation_ref for row in templates],
        )
        result = project_state_calibration(templates, instances, as_of=as_of)
        return {**result, "snapshot": snapshot}

    def read_single_template(
        self,
        ledger_scope: ExecutionLedgerReadScope,
        template: CalibrationTemplate,
        *,
        as_of: datetime,
    ):
        instances = read_template_candidate_instances(self.repo, template.part_no, template.operation_ref)
        self.ledger.seed_operations(ledger_scope, instances)
        refs = [row["operation_ref"] for row in instances]
        facts = self.ledger.load_many(ledger_scope, refs)
        projections = {
            row.operation_ref: row
            for row in project_loaded_facts(facts, include_history=False)
        }
        result = project_single_template_calibration(
            template,
            instances,
            projections,
            as_of=as_of,
        )
        return {**result, "report_histories": facts["reports"]}
