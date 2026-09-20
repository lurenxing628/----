"""One caller-owned SQLite snapshot and one canonical execution projection.

The query repository returns bounded rows only; schema readiness, missing identities
and size limits are ruled on here before anything is projected.
"""

from contextlib import contextmanager

from core.models.workbench_calibration import MAX_OPERATIONS, MAX_TEMPLATES, CalibrationTemplate
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_execution_input import MAX_FACT_ROWS, public_ref
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository

from .integrity import validate_report_histories
from .template_lineage_calibration import project_lineage_calibration
from .template_lineage_query import TemplateLineageQuery


def require_calibration_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("calibration_source_unavailable", "模板永久身份或修订结构未就绪，本次读取没有补表或补身份。")


def read_templates(repo, query):
    if query.part_ref is not None and not repo.part_exists(query.part_ref):
        raise WorkbenchCommandRejected("entity_not_found", "所选零件已失效，请重新选择。", 404)
    rows = repo.template_rows(query.part_ref, MAX_TEMPLATES)
    if len(rows) > MAX_TEMPLATES:
        raise WorkbenchCommandRejected("query_too_large", "模板范围超过10000道，请按零件缩小范围；未截断数据。", 413)
    result = []
    for row in rows:
        if row["operation_ref"] is None or row["part_ref"] is None or type(row["revision"]) is not int or row["revision"] < 1:
            raise WorkbenchCommandRejected("calibration_source_unavailable", "模板或所属零件的永久身份缺失，不能补配。")
        public_ref(row["operation_ref"])
        public_ref(row["part_ref"])
        source = row["source"] if row["source"] in ("internal", "external") else "unknown"
        text = " ".join(str(row[key] or "") for key in ("part_no", "part_name", "op_type_name", "seq"))
        if query.source not in (None, source) or query.query.casefold() not in text.casefold():
            continue
        result.append(CalibrationTemplate(row["operation_ref"], row["revision"], row["part_ref"],
            row["part_no"], row["part_name"], row["seq"], row["op_type_name"], row["source"], row["unit_hours"]))
    return result


def read_candidate_instances(repo, part_numbers):
    """Same-part records are audit candidates only, NOT template sample matches."""
    result = repo.candidate_instance_rows(part_numbers, MAX_OPERATIONS)
    if len(result) > MAX_OPERATIONS:
        raise WorkbenchCommandRejected("query_too_large", "待核对执行工序超过10000道，请缩小零件范围；未截断样本。", 413)
    if any(row["operation_ref"] is None for row in result):
        raise WorkbenchCommandRejected("calibration_source_unavailable", "执行实例永久身份缺失，不能按批次号或工序号补配。")
    return result


def read_report_heads(repo, operation_refs):
    result = repo.report_head_refs(operation_refs, MAX_FACT_ROWS)
    if len(result) > MAX_FACT_ROWS:
        raise WorkbenchCommandRejected("query_too_large", "报工来源超过50000条，未截断历史。", 413)
    return result


class CalibrationFacts:
    def __init__(self, conn, *, as_of):
        self.repo = WorkbenchCalibrationQueryRepository(conn)
        self.as_of = as_of
        self.ledger = ExecutionLedgerService(conn, clock=lambda: self.as_of)
        self.lineage = TemplateLineageQuery(conn)

    @contextmanager
    def read_snapshot(self, *, clock=None):
        with self.ledger.read_snapshot():
            require_calibration_schema(self.repo)
            if clock is not None:
                self.as_of = clock()
            yield self.as_of

    def read(self, query, *, bind_snapshot=None):
        templates = read_templates(self.repo, query)
        instances = read_candidate_instances(self.repo, [row.part_no for row in templates])
        refs = [row["operation_ref"] for row in instances]
        facts = self.ledger.load(refs)
        lineage = self.lineage.read(refs)
        fingerprint = input_fingerprint(plain_plan_facts({"templates": [row.to_dict() for row in templates],
            "instances": instances, "lineage": {key: value for key, value in lineage.items() if key != "lineages"},
            "execution": {**facts, "unresolved": sorted(facts["unresolved"])}}))
        snapshot = bind_snapshot(fingerprint) if bind_snapshot is not None else None
        validate_report_histories(facts, read_report_heads(self.repo, refs), self.as_of)
        projections = {row.operation_ref: row for row in self.ledger.project_loaded(facts, contexts=False)}
        result = project_lineage_calibration(templates, instances, projections, lineage, as_of=self.as_of)
        return {**result, "fingerprint": fingerprint, "snapshot": snapshot}
