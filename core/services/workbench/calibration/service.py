"""Read-model composition, independent from Flask transport and export rendering."""

from datetime import datetime

from core.models.workbench_calibration import METHOD_VERSION, closed_capabilities, write_blockers
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref
from core.services.execution.ledger_reader import ExecutionLedgerReadScope

from .facts import CalibrationFacts, read_single_template_row
from .samples import ensure_sample_reports, ensure_sample_revision, populate_selected_revisions
from .table import filter_rows

_NOT_IN_FILTER_MESSAGE = "这条建议不在当前筛选结果里。数据可能已更新，请刷新后重新选择。"
_LIST_OMITTED_FIELDS = ("sample_refs", "sample_revisions", "exclusion_reasons", "template_snapshot")


def filtered_suggestions(rows, query, *, cell_cache=None, sort):
    selected = [
        row
        for row in rows
        if (query.status == "all" or row["status"] == query.status)
        and (query.deviation == "all" or row["over_20_percent"])
    ]
    selected = filter_rows(selected, query.column_filters, cell_cache=cell_cache)
    if not sort:
        return selected
    # Unknowns remain last in both directions; identity is the stable tie breaker.
    known = [row for row in selected if row[query.sort] is not None]
    unknown = [row for row in selected if row[query.sort] is None]
    known.sort(key=lambda row: row["suggestion_ref"])
    known.sort(key=lambda row: row[query.sort], reverse=query.direction == "desc")
    unknown.sort(key=lambda row: row["suggestion_ref"])
    return known + unknown


class WorkbenchCalibrationService(CalibrationFacts):
    def workspace(self, facts, query, snapshot, *, export=False):
        rows = filtered_suggestions(facts["rows"], query, sort=True)
        meta_fields = snapshot or {}
        start = (query.number - 1) * query.size
        page_rows = rows[start : start + query.size]
        items = [
            {
                **{key: value for key, value in row.items() if key not in _LIST_OMITTED_FIELDS},
                **meta_fields,
            }
            for row in page_rows
        ]
        if export:
            report_map = self.repo.selected_report_refs([ref for row in rows for ref in row["sample_refs"]])
            export_rows = populate_selected_revisions(
                rows, facts["samples_by_ref"], report_map, snapshot=meta_fields
            )
        else:
            export_rows = rows
        data = {
            "scope": query.scope(),
            "method_version": METHOD_VERSION,
            "source_constraints": facts["source_constraints"],
            "lineage_available": facts["lineage_available"],
            "capabilities": closed_capabilities(),
            "blocked_reasons": write_blockers(),
            "summary": {
                "total": len(rows),
                "suggested": sum(row["status"] == "suggested" for row in rows),
                "insufficient_data": sum(row["status"] == "insufficient_data" for row in rows),
                "over_20_percent": sum(row["over_20_percent"] for row in rows),
            },
            "exports": {
                "url": "/api/workbench/v1/calibration/export",
                "formats": ["csv", "xlsx"],
                "scope": "all_filtered_suggestions",
                "snapshot_required": True,
            },
            "items": items,
            "page": {
                "number": query.number,
                "size": query.size,
                "total": len(rows),
                "total_pages": (len(rows) + query.size - 1) // query.size,
                "has_more": start + query.size < len(rows),
            },
        }
        return data, export_rows

    def read_detail(
        self,
        ledger_scope: ExecutionLedgerReadScope,
        query,
        suggestion_ref: str,
        *,
        as_of: datetime,
        bind_snapshot=None,
    ):
        public_ref(suggestion_ref)
        part_identity, snapshot = self._resolve_part_and_snapshot(
            ledger_scope, query, bind_snapshot=bind_snapshot
        )
        template = read_single_template_row(
            self.repo, suggestion_ref, query, part_identity=part_identity
        )
        if template is None:
            raise WorkbenchCommandRejected("entity_not_found", _NOT_IN_FILTER_MESSAGE, 404)
        detail = self.read_single_template(ledger_scope, template, as_of=as_of)
        row = detail["row"]
        if not filtered_suggestions([row], query, sort=False):
            raise WorkbenchCommandRejected("entity_not_found", _NOT_IN_FILTER_MESSAGE, 404)
        samples = [
            ensure_sample_reports(
                ensure_sample_revision(sample),
                report_histories=detail["report_histories"],
            )
            for sample in detail["linked_samples"] + detail["unbound_samples"]
        ]
        meta_fields = snapshot or {}
        data = {
            "scope": query.scope(),
            "method_version": METHOD_VERSION,
            "source_constraints": detail["source_constraints"],
            "lineage_available": detail["lineage_available"],
            "capabilities": closed_capabilities(),
            "blocked_reasons": write_blockers(),
            "exports": {
                "url": "/api/workbench/v1/calibration/export",
                "formats": ["csv", "xlsx"],
                "scope": "all_filtered_suggestions",
                "snapshot_required": True,
            },
            "suggestion": {**row, **meta_fields},
            "samples": samples,
            "candidate_scope_basis": "template_ref_and_same_part_unbound",
        }
        return data, snapshot
