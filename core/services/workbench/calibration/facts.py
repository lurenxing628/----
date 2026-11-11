"""One caller-owned SQLite snapshot and one canonical execution projection.

The query repository returns bounded rows only; schema readiness, missing identities
and size limits are ruled on here before anything is projected.
"""

from datetime import datetime
from typing import ContextManager

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.workbench_calibration import MAX_OPERATIONS, MAX_TEMPLATES, CalibrationTemplate
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref
from core.services.execution.ledger_reader import ExecutionLedgerReadScope, project_loaded_facts
from core.services.scheduler.template_lineage_query import TemplateLineageQuery
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.source_revisions import CALIBRATION_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository

from .template_lineage_calibration import project_lineage_calibration


def _lineage_template_row(row):
    result = {key: value for key, value in row.items() if key not in ("operation_ref", "revision", "part_name")}
    result["template_operation_ref"] = row["operation_ref"]
    result["template_revision"] = row["revision"]
    result["part_ref"] = row["part_ref"]
    return result


def read_templates(repo, query, *, lineage_templates, part_identity):
    part_no = part_identity["entity_key"] if part_identity is not None else None
    rows = repo.template_rows(part_no, MAX_TEMPLATES)
    if len(rows) > MAX_TEMPLATES:
        raise WorkbenchCommandRejected("query_too_large", "模板范围超过10000道，请按零件缩小范围；未截断数据。", 413)
    result = []
    seen_part_refs = set()
    needle = query.query.casefold()
    for row in rows:
        if row["operation_ref"] is None or row["part_ref"] is None or type(row["revision"]) is not int or row["revision"] < 1:
            raise WorkbenchCommandRejected("calibration_source_unavailable", "模板或所属零件的永久身份缺失，不能补配。")
        public_ref(row["operation_ref"])
        if row["part_ref"] not in seen_part_refs:
            public_ref(row["part_ref"])
            seen_part_refs.add(row["part_ref"])
        lineage_templates[row["operation_ref"]] = _lineage_template_row(row)
        source = row["source"] if row["source"] in OPERATION_SOURCES else "unknown"
        if query.source not in (None, source):
            continue
        if needle:
            text = " ".join(str(row[key] or "") for key in ("part_no", "part_name", "op_type_name", "seq"))
            if needle not in text.casefold():
                continue
        result.append(CalibrationTemplate(row["operation_ref"], row["revision"], row["part_ref"],
            row["part_no"], row["part_name"], row["seq"], row["op_type_name"], source, row["unit_hours"]))
    return result


def read_candidate_instances(repo, part_numbers):
    """Same-part records are audit candidates only, NOT template sample matches."""
    result = repo.candidate_instance_rows(part_numbers, MAX_OPERATIONS)
    if len(result) > MAX_OPERATIONS:
        raise WorkbenchCommandRejected("query_too_large", "待核对执行工序超过10000道，请缩小零件范围；未截断样本。", 413)
    if any(row["operation_ref"] is None for row in result):
        raise WorkbenchCommandRejected("calibration_source_unavailable", "执行实例永久身份缺失，不能按批次号或工序号补配。")
    return result


class CalibrationFacts:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchCalibrationQueryRepository(conn)
        self.ledger = ExecutionLedgerService(conn)
        self.lineage = TemplateLineageQuery(conn)

    def read_snapshot(self) -> ContextManager[ExecutionLedgerReadScope]:
        return self.ledger.read_snapshot()

    def read(self, ledger_scope: ExecutionLedgerReadScope, query, *, as_of: datetime, bind_snapshot=None):
        snapshot = None
        part_identity = None
        if query.part_ref is not None:
            part_identity = self.repo.part_identity(query.part_ref)
            if part_identity is None:
                raise WorkbenchCommandRejected("entity_not_found", "所选零件已失效，请重新选择。", 404)
        if bind_snapshot is not None:
            content = {
                "revisions": read_source_revisions(self.conn, CALIBRATION_SOURCE_KEYS),
                "ledger_revision": self.ledger.revision_clock(ledger_scope),
                "scope": query.scope(),
            }
            snapshot = bind_snapshot(content)
        templates_by_ref = {}
        templates = read_templates(self.repo, query, lineage_templates=templates_by_ref, part_identity=part_identity)
        instances = read_candidate_instances(self.repo, [row.part_no for row in templates])
        self.ledger.seed_operations(ledger_scope, instances)
        current_by_ref = {row["operation_ref"]: row for row in instances}
        refs = [row["operation_ref"] for row in instances]
        facts = self.ledger.load(ledger_scope, refs)
        lineage = self.lineage.read_partial(
            refs,
            current_by_ref=current_by_ref,
            templates_by_ref=templates_by_ref,
        )
        projections = {
            row.operation_ref: row
            for row in project_loaded_facts(facts, include_history=False)
        }
        result = project_lineage_calibration(
            templates,
            instances,
            projections,
            lineage,
            as_of=as_of,
        )
        return {**result, "snapshot": snapshot, "report_histories": facts["reports"]}
