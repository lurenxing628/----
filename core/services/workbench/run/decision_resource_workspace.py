"""Coordinate the saved resource view and summary in one archived read scope."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import local_time, reject
from core.services.workbench.facts.candidate_store import CandidateStore

from .decision import decision_summary
from .decision_queries import parse_page
from .decision_resources import normalize_resource_filters, resource_details
from .decision_source import DecisionSource


def _resource_view(query):
    query = dict(query or {})
    fields = ("resource_kind", "resource_ref", "pressure_filter", "sort", "order", "grain",
              "pressure_threshold", "display_start", "display_end")
    filters = normalize_resource_filters("resources", **{key: query[key] for key in fields if key in query})
    value = {key: filters[key] for key in fields if filters[key] is not None}
    value.update(page=parse_page(query.get("page", 1)), size=parse_page(query.get("size", 20), size=True),
                 heatmap_page=parse_page(query.get("heatmap_page", 1)), heatmap_size=parse_page(query.get("heatmap_size", 7)))
    if value["heatmap_size"] not in (7, 14, 31):
        reject("invalid_input", "资源热力图每页请选择7、14或31个时段。", 422)
    if "snapshot_ref" in query:
        value["snapshot_ref"] = query["snapshot_ref"]
    return value, filters


def normalize_saved_resource_view(query, scope):
    """Drop only the same expired references and display range as storedQuery."""
    value = dict(query)
    resource_ref = value.get("resource_ref")
    if resource_ref is not None and resource_ref not in scope["resource_refs"][value["resource_kind"]]:
        value.pop("resource_ref")
        value.pop("snapshot_ref", None)
        value["page"] = 1
    if "display_start" in value and (local_time(value["display_start"]) < local_time(scope["range_start"])
            or local_time(value["display_end"]) > local_time(scope["range_end"])):
        value.pop("display_start")
        value.pop("display_end")
        value.pop("snapshot_ref", None)
        value["heatmap_page"] = 1
    return value


def read_resource_workspace(conn, run_ref, *, resource_query=None, **summary_query):
    saved_view, filters = _resource_view(resource_query)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, **summary_query)
        summary = decision_summary(source)
        effective = normalize_saved_resource_view(saved_view, source.scope)
        filters.update({key: effective.get(key) for key in ("resource_ref", "display_start", "display_end")})
        result, error = None, None
        if source.selected is not None and source.selected["status"] == "completed":
            try:
                result = resource_details(source, filters, **{key: effective[key] for key in ("page", "size", "heatmap_page", "heatmap_size")})
            except WorkbenchCommandRejected as exc:
                error = exc
        return summary, result, effective, error, source.state()
