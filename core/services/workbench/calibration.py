"""Read-model composition, independent from Flask transport and export rendering."""

from core.models.workbench_calibration import METHOD_VERSION, closed_capabilities, write_blockers
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref

from .calibration_facts import CalibrationFacts
from .calibration_table import filter_rows


def filtered_suggestions(rows, query):
    selected = [row for row in rows if (query.status == "all" or row["status"] == query.status)
                and (query.deviation == "all" or row["over_20_percent"])]
    selected = filter_rows(selected, query.column_filters)
    # Unknowns remain last in both directions; identity is the stable tie breaker.
    known = [row for row in selected if row[query.sort] is not None]
    unknown = [row for row in selected if row[query.sort] is None]
    known.sort(key=lambda row: row["suggestion_ref"])
    known.sort(key=lambda row: row[query.sort], reverse=query.direction == "desc")
    unknown.sort(key=lambda row: row["suggestion_ref"])
    return known + unknown


class WorkbenchCalibrationService:
    def __init__(self, conn, *, as_of):
        self.facts = CalibrationFacts(conn, as_of=as_of)

    def read_snapshot(self, *, clock=None):
        return self.facts.read_snapshot(clock=clock)

    def read(self, query, *, bind_snapshot=None):
        """Caller holds read_snapshot until the scope token has been checked."""
        return self.facts.read(query, bind_snapshot=bind_snapshot)

    @staticmethod
    def workspace(facts, query, snapshot, *, suggestion_ref=None):
        rows = [{**row, **snapshot} for row in filtered_suggestions(facts["rows"], query)]
        data = {"scope": query.scope(), "method_version": METHOD_VERSION,
                "source_constraints": facts["source_constraints"], "lineage_available": facts["lineage_available"],
                "capabilities": closed_capabilities(), "blocked_reasons": write_blockers(),
                "summary": {"total": len(rows), "suggested": sum(row["status"] == "suggested" for row in rows),
                            "insufficient_data": sum(row["status"] == "insufficient_data" for row in rows),
                            "over_20_percent": sum(row["over_20_percent"] for row in rows)},
                "exports": {"url": "/api/workbench/v1/calibration/export", "formats": ["csv", "xlsx"],
                            "scope": "all_filtered_suggestions", "snapshot_required": True}}
        if suggestion_ref is not None:
            public_ref(suggestion_ref)
            row = next((row for row in rows if row["suggestion_ref"] == suggestion_ref), None)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "建议不在当前筛选快照内，不能改指同号模板。", 404)
            linked = facts["samples_by_template"].get(row["template_operation_ref"], [])
            unbound = facts["unbound_samples_by_part"].get(row["part_no"], [])
            data.update(suggestion=row, samples=linked + unbound,
                        candidate_scope_basis="template_ref_and_same_part_unbound")
        else:
            start = (query.number - 1) * query.size
            data.update(items=rows[start:start + query.size], page={"number": query.number, "size": query.size,
                "total": len(rows), "total_pages": (len(rows) + query.size - 1) // query.size,
                "has_more": start + query.size < len(rows)})
        return data, rows
