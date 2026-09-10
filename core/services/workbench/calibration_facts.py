"""One caller-owned SQLite snapshot and one canonical execution projection."""

from contextlib import contextmanager

from core.models.workbench_command import input_fingerprint
from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository

from .calibration_integrity import validate_report_histories
from .execution_ledger import ExecutionLedgerService
from .plan_fact_serialization import plain_plan_facts
from .template_lineage_calibration import project_lineage_calibration
from .template_lineage_query import TemplateLineageQuery


class CalibrationFacts:
    def __init__(self, conn, *, as_of):
        self.repo = WorkbenchCalibrationQueryRepository(conn)
        self.as_of = as_of
        self.ledger = ExecutionLedgerService(conn, clock=lambda: self.as_of)
        self.lineage = TemplateLineageQuery(conn)

    @contextmanager
    def read_snapshot(self, *, clock=None):
        with self.ledger.read_snapshot():
            self.repo.require_schema()
            if clock is not None:
                self.as_of = clock()
            yield self.as_of

    def read(self, query, *, bind_snapshot=None):
        templates = self.repo.templates(query)
        instances = self.repo.candidate_instances(row.part_no for row in templates)
        refs = [row["operation_ref"] for row in instances]
        facts = self.ledger.load(refs)
        lineage = self.lineage.read(refs)
        fingerprint = input_fingerprint(plain_plan_facts({"templates": [row.to_dict() for row in templates],
            "instances": instances, "lineage": {key: value for key, value in lineage.items() if key != "lineages"},
            "execution": {**facts, "unresolved": sorted(facts["unresolved"])}}))
        snapshot = bind_snapshot(fingerprint) if bind_snapshot is not None else None
        validate_report_histories(facts, self.repo.report_heads(refs), self.as_of)
        projections = {row.operation_ref: row for row in self.ledger.project_loaded(facts, contexts=False)}
        result = project_lineage_calibration(templates, instances, projections, lineage, as_of=self.as_of)
        return {**result, "fingerprint": fingerprint, "snapshot": snapshot}
