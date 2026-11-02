"""Coordinate the saved resource view and summary in one archived read scope."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import local_time

from .decision import decision_summary
from .decision_queries import parse_page
from .decision_resources import normalize_resource_filters, parse_heatmap_size, resource_details, resource_view
from .decision_session import decision_read, decision_snapshot_scope


def _resource_view(query):
    fields = ("resource_kind", "resource_ref", "pressure_filter", "sort", "order", "grain",
              "pressure_threshold", "display_start", "display_end")
    filters = normalize_resource_filters("resources", **{key: query[key] for key in fields if key in query})
    value = {key: filters[key] for key in fields if filters[key] is not None}
    value.update(page=parse_page(query.get("page", 1)), size=parse_page(query.get("size", 20), size=True),
                 heatmap_page=parse_page(query.get("heatmap_page", 1)), heatmap_size=parse_heatmap_size(query.get("heatmap_size", 7)))
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


def read_resource_workspace(conn, run_ref, *, resource_query, bind_snapshot, **summary_query):
    """The summary and its saved resource view, both bound before either is projected.

    ``bind_snapshot(scope, state, resource)`` binds the summary and, when the resource view is shown,
    ``resource`` = (its filters, its effective token). It returns (snapshot, resource_snapshot, resource_error);
    a resource view whose own token is stale stays an independent error beside the summary.
    """
    saved_view, filters = _resource_view(resource_query)
    with decision_read(conn, run_ref, **summary_query) as source:
        effective = normalize_saved_resource_view(saved_view, source.scope)
        filters.update({key: effective.get(key) for key in ("resource_ref", "display_start", "display_end")})
        view, error = None, None
        if source.selected is not None and source.selected["status"] == "completed":
            try:
                filters, view = resource_view(source, filters, heatmap_page=effective["heatmap_page"],
                                              heatmap_size=effective["heatmap_size"])
            except WorkbenchCommandRejected as exc:
                error = exc
        snapshot, resource_snapshot, bind_error = bind_snapshot(
            decision_snapshot_scope(source), source.state(),
            (filters, effective.get("snapshot_ref")) if view is not None else None)
        if bind_error is not None:
            error = bind_error
        summary = decision_summary(source)
        result = None
        if resource_snapshot is not None:
            try:
                result = resource_details(source, filters, view, page=effective["page"], size=effective["size"])
            except WorkbenchCommandRejected as exc:
                error = exc
        return summary, result, effective, error, snapshot, resource_snapshot
