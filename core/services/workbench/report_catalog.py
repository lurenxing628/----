"""Existing report calculations and exporters, preserving their distinct scopes."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_report import ReportScope
from core.services.report import calculations
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from core.services.report.exporters.xlsx import (
    export_downtime_impact_xlsx,
    export_overdue_xlsx,
    export_utilization_xlsx,
)

from .report_exports import TOPIC_TITLES, ensure_export_size, metadata

CATALOG_COLUMNS = {
    "overdue": [("batch_label", "批次"), ("part_name", "零件"), ("bucket_label", "风险类别"),
                ("due_date", "交期"), ("finish_time", "计划完工"), ("delay_hours", "预计超期（小时）")],
    "utilization": [("resource_label", "资源"), ("resource_kind_label", "类型"), ("hours", "计划负荷（小时）"),
                    ("task_count", "计划任务数"), ("capacity_hours", "可用工时（小时）"), ("utilization_percent", "计划利用率（%）")],
    "downtime": [("resource_label", "设备"), ("downtime_hours", "停机工时（小时）"), ("downtime_count", "停机次数"),
                 ("schedule_overlap_hours", "计划重叠（小时）"), ("schedule_overlap_count", "计划重叠次数")],
}
CATALOG_CONTEXT = {
    "overdue": ("当前正式计划与批次交期", "这里看的是计划交付风险，不是实际晚完成记录；没排上的批次和交期填得不对的批次分开列。"),
    "utilization": ("当前正式计划与班表产能", "计划负荷不是实际加工工时；只统计落在计划时段里的部分。"),
    "downtime": ("当前正式计划与有效停机记录", "停机只认已登记的停机记录，不把报工空档当成停机。"),
}


def catalog_facts(reader, scope):
    _, plan, version, span = reader.current_plan(ReportScope(source=scope.source, plan_ref=scope.plan_ref))
    scope = replace(scope, plan_ref=plan["plan_ref"])
    if scope.kind != "overdue":
        scope = replace(scope, window_date_from=scope.window_date_from or span["start"][:10],
                        window_date_to=scope.window_date_to or span["end"][:10])
        ensure_report_date_range_within_limit(datetime.fromisoformat(scope.window_date_from).date(), datetime.fromisoformat(scope.window_date_to).date())
    engine = reader.engine
    if scope.kind == "overdue":
        raw = engine._fetch_overdue_base_rows_for_plan(version, ROLE_ADOPTED, None)
        report = None
        collections = [("batch", raw)]
    else:
        report = getattr(engine, "utilization" if scope.kind == "utilization" else "downtime_impact")(
            version, scope.window_date_from, scope.window_date_to, plan_role=ROLE_ADOPTED, scenario_id=None)
        raw = report
        collections = [("machine", report.get("machines", [])), ("operator", report.get("operators", []))]
    identities = {}
    for kind, rows in collections:
        keys = {str(row[kind + "_id"]) for row in rows}
        mapping = reader.plans.entities.active_map(kind, sorted(keys))
        if set(mapping) != keys:
            raise WorkbenchCommandRejected("identity_missing", "这张报表里有批次或资源的编号读不到，报表没有生成。请到资料总览核对后再打开。")
        identities[kind] = {key: {"ref": value.ref, "revision": value.revision} for key, value in mapping.items()}
    fingerprint = input_fingerprint({"plan_revision": reader.plans.references.read_revision(), "plan": plan, "raw": raw, "identities": identities})
    return {"scope": scope, "plan": plan, "raw": raw, "report": report, "fingerprint": fingerprint, "identities": identities}


def _identity(facts, kind, key):
    return facts["identities"][kind][str(key)]["ref"]


def _overdue_rows(facts, snapshot):
    rows, source_rows = [], []
    scheduled, unscheduled, invalid, _ = calculations.compute_overdue_bucket_groups(facts["raw"], now_dt=datetime.fromisoformat(snapshot["as_of"]))
    for row in scheduled + invalid + unscheduled:
        public = {key: row.get(key) for key, _ in CATALOG_COLUMNS["overdue"]}
        public.update({"batch_ref": _identity(facts, "batch", row["batch_id"]), "batch_label": row["batch_id"]})
        rows.append(public)
        source_rows.append(row)
    return rows, source_rows


def _resource_rows(facts):
    scope, rep = facts["scope"], facts["report"]
    rows, source_rows = [], []
    for kind, collection in (("machine", "machines"), ("operator", "operators")):
        for row in rep.get(collection, []):
            public = {key: row.get(key) for key, _ in CATALOG_COLUMNS[scope.kind]}
            public.update({"resource_ref": _identity(facts, kind, row[kind + "_id"]),
                "resource_label": row.get(kind + "_name") or "名称未填写", "resource_kind": kind,
                "resource_kind_label": "设备" if kind == "machine" else "人员"})
            if scope.kind == "utilization":
                public["utilization_percent"] = None if row.get("utilization") is None else round(row["utilization"] * 100, 2)
            rows.append(public)
            source_rows.append({**row, "resource_kind": kind})
    return rows, source_rows


def catalog_workspace(reader, facts, snapshot, page):
    scope, rep = facts["scope"], facts["report"]
    rows, source_rows = _overdue_rows(facts, snapshot) if scope.kind == "overdue" else _resource_rows(facts)
    source_by_key = {}
    for public, raw in zip(rows, source_rows):
        source_by_key[public.get("batch_ref") or public["resource_ref"]] = raw
    query = scope.query.strip().casefold()
    rows = [row for row in rows if query in " ".join(str(row.get(key) or "") for key, _ in CATALOG_COLUMNS[scope.kind]).casefold()]
    ordered, visible, pagination = page.apply(rows, [key for key, _ in CATALOG_COLUMNS[scope.kind]])
    selected = [source_by_key[row.get("batch_ref") or row["resource_ref"]] for row in ordered]
    provenance, gap = CATALOG_CONTEXT[scope.kind]
    data = {"plan": facts["plan"], "scope": scope.scope(), "topic": scope.kind,
            "rows": visible, "columns": [{"key": key, "label": label} for key, label in CATALOG_COLUMNS[scope.kind]],
            "summary": {"rows": len(ordered)}, "page": pagination,
            "provenance": provenance, "data_gaps": [gap]}
    if rep and rep.get("report_degraded"):
        data["data_gaps"].append("有一部分原始数据不可用，没有参与本表计算，请核对原始记录。")
    return data, ordered, selected


def export_catalog_xlsx(reader, data, selected, snapshot):
    if not selected:
        raise WorkbenchCommandRejected("empty_export", "当前筛选范围里没有可导出的结果，没有开始下载。请放宽筛选条件后重试。", 422)
    ensure_export_size(reader.engine, len(selected))
    kind = data["topic"]
    def render(write_only=False):
        options = {"summary_rows": metadata(data, snapshot), "write_only": write_only}
        if kind == "overdue":
            return export_overdue_xlsx(selected, **options)
        if kind == "downtime":
            return export_downtime_impact_xlsx(selected, **options)
        return export_utilization_xlsx([row for row in selected if row["resource_kind"] == "machine"],
                                      [row for row in selected if row["resource_kind"] == "operator"], **options)
    return reader.engine._build_xlsx_export(report_name="其他报表", filename=TOPIC_TITLES[kind] + ".xlsx",
        estimated_rows=len(selected), build_direct=render, build_stream=lambda: render(True))
