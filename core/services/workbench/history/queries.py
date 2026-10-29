"""One read-only history snapshot for paging, original details and complete files."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_decision_history import (
    HISTORY_VERSION,
    history_snapshot_scope,
    normalize_history_query,
    reject_history,
)
from core.services.workbench.facts.decision_metrics import metric_definitions
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot

from .catalog import read_history_catalog
from .metric_gate import gate_history_metric
from .projection import (
    chronological_key,
    comparison_conclusion,
    condition_pair,
    project_entry,
    reason,
    trend_projection,
    window_comparable,
)
from .reading import HistoryReader


def _filtered(descriptor, query):
    if descriptor["timeline"] != query["timeline"] or query["state"] != "all" and descriptor["state"] != query["state"]:
        return False
    if query["date_from"] is not None:
        occurred = descriptor["occurred_at"]
        return occurred is not None and query["date_from"] <= occurred[:10] <= query["date_to"]
    return True


def _page(rows, number, size, *, all_rows):
    start = (number - 1) * size
    return (list(rows) if all_rows else rows[start:start + size],
            {"number": number, "size": size, "total": len(rows), "has_more": False if all_rows else start + size < len(rows)})


def _descriptor(entries, reference):
    if reference is None:
        return None
    value = entries.get(reference)
    if value is None:
        reject_history("所选历史条目或基准运行已不存在，请刷新历史。", "entity_not_found", 404)
    return value


def _read(conn, values, *, all_rows):
    query = normalize_history_query(values)
    definitions = metric_definitions()
    by_metric = {row["key"]: row for row in definitions}
    if set(query["metric_keys"]) - set(by_metric):
        reject_history("指标列表含目录外项目，请从历史指标目录重新选择。")
    with candidate_read_snapshot(conn), read_evidence_scope(conn):
        catalog, state = read_history_catalog(conn)
        descriptors = {row["entry_ref"]: row for row in catalog}
        selected_descriptor = _descriptor(descriptors, query["selected_entry_ref"])
        reference_descriptor = _descriptor(descriptors, "run:" + query["reference_run_ref"] if query["reference_run_ref"] else None)
        rows = [row for row in catalog if _filtered(row, query)]
        dated = sorted((row for row in rows if row["occurred_at"] is not None), key=chronological_key,
                       reverse=query["order"] == "desc")
        rows = dated + sorted((row for row in rows if row["occurred_at"] is None), key=lambda row: row["entry_ref"])
        page_rows, page = _page(rows, query["page"], query["size"], all_rows=all_rows)
        reader, projected, pairs = HistoryReader(conn, catalog=catalog), {}, {}

        def entry(descriptor):
            if descriptor is None:
                return None
            key = descriptor["entry_ref"]
            if key not in projected:
                projected[key] = project_entry(reader, descriptor, query)
            return projected[key]

        entries = [entry(row) for row in page_rows]
        selected, reference = entry(selected_descriptor), entry(reference_descriptor)
        pair = condition_pair(reader, reference_descriptor, selected_descriptor, selected, query, pairs,
                              include_rows=True, all_rows=all_rows)
        conditions = pair["conditions"]
        deltas = {}
        for key in query["metric_keys"]:
            if selected is not None and reference is not None:
                deltas[key] = gate_history_metric(by_metric[key], reference["metrics"][key], selected["metrics"][key],
                    production_state=pair["conditions"]["state"], objective_state=pair["objective"]["state"],
                    window_comparable=window_comparable(reference, selected, by_metric[key]))
            else:
                deltas[key] = {"value": None, "state": "unavailable", "direction": "neutral",
                    "reference_value": reference["metrics"][key]["value"] if reference else None,
                    "selected_value": selected["metrics"][key]["value"] if selected else None,
                    "reason": reason("history_pair_required", "比较指标需要实际历史条目和明确基准运行。")}
        comparison = {"mode": query["comparison"], "conditions": conditions,
            "configurations": pair["configurations"], "objective": pair["objective"], "metric_deltas": deltas,
            "conclusion": comparison_conclusion(query["comparison"], pair, deltas, selected is not None and reference is not None)}
        trend = {"point_scope": "current_page", "order": "asc", "points": []} if all_rows else trend_projection(
            reader, entries, descriptors, reference, reference_descriptor, query, by_metric, pairs)
        absolute = query["range_start"] is not None
        policy = {"mode": "absolute" if absolute else "fixed_days", "start": query["range_start"], "end": query["range_end"],
            "days": None if absolute else query["resource_window_days"], "anchor": "common_absolute_window" if absolute else "source_start",
            "time_basis": "factory_local", "boundary": "half_open"}
        data = {"history_version": HISTORY_VERSION, "filters": {key: value for key, value in query.items() if key != "snapshot_ref"},
            "entries": entries, "page": page, "totals": {"run": sum(row["timeline"] == "run" for row in catalog),
                "official": sum(row["timeline"] == "official" for row in catalog), "filtered": len(rows)},
            "metric_definitions": definitions, "selection": {"entry": selected, "reference": reference},
            "comparison": comparison, "trend": trend, "resource_window": policy}
        # Immutable archives bind permanent source identities and known gaps;
        # the directory's existing identity clock covers its mutable official bindings.
        state["source_anchors"] = [reader.source_state(descriptor) for descriptor in (selected_descriptor, reference_descriptor)
                                   if descriptor is not None]
        return data, history_snapshot_scope(query), state


def read_decision_history(conn, query):
    return _read(conn, query, all_rows=False)


def read_history_all(conn, query):
    return _read(conn, query, all_rows=True)
