"""Existing report calculations and exporters, preserving their distinct scopes."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import ReportScope
from core.services.common.overdue_calculations import compute_overdue_bucket_groups
from core.services.report.exporters.xlsx import (
    export_downtime_impact_xlsx,
    export_overdue_xlsx,
    export_utilization_xlsx,
)
from core.services.report.utilization import utilization_availability_note, utilization_percent

from .exports import TOPIC_TITLES, ensure_export_size, metadata

CATALOG_COLUMNS = {
    "overdue": [("batch_label", "批次"), ("part_name", "零件"), ("bucket_label", "风险类别"),
                ("due_date", "交期"), ("finish_time", "计划完工"), ("delay_hours", "预计超期（小时）")],
    "utilization": [("resource_label", "资源"), ("resource_kind_label", "类型"), ("hours", "班表内占用（小时）"),
                    ("task_count", "计划任务数"), ("capacity_hours", "可用工时（小时）"), ("utilization_percent", "整窗占用率（%）"),
                    ("summed_load_hours", "累计负荷（小时）"), ("overlap_hours", "重叠负荷（小时）"),
                    ("outside_calendar_hours", "班表外占用（小时）"), ("availability_note", "计算说明")],
    "downtime": [("resource_label", "设备"), ("downtime_hours", "停机工时（小时）"), ("downtime_count", "停机次数"),
                 ("schedule_overlap_hours", "计划重叠（小时）"), ("schedule_overlap_count", "计划重叠次数")],
}
CATALOG_CONTEXT = {
    "overdue": ("当前正式计划与批次交期", "按正式计划评估交付风险，未排产和交期异常批次单列。"),
    "utilization": ("当前正式计划与逐资源工作日历", "整窗占用率按班表内占用并集 ÷ 可用工时计算；设备扣除停机，人员使用个人日历。重叠负荷与班表外占用单列，班表效率不改变时间轴占用。"),
    "downtime": ("当前正式计划与有效停机记录", "按已登记的停机记录统计。"),
}


def catalog_facts(reader, scope):
    _, plan, resolution, span = reader.current_plan_metadata(ReportScope(source=scope.source, plan_ref=scope.plan_ref))
    scope_updates = {"plan_ref": plan["plan_ref"]}
    if scope.kind != "overdue":
        scope_updates["window_date_from"] = scope.window_date_from or span["start"][:10]
        scope_updates["window_date_to"] = scope.window_date_to or span["end"][:10]
    scope = replace(scope, **scope_updates)
    engine = reader.engine
    if scope.kind == "overdue":
        raw = engine._fetch_overdue_base_rows_for_plan(resolution)
        report = None
        collections = [("batch", raw)]
    else:
        report = (engine.utilization if scope.kind == "utilization" else engine.downtime_impact)(
            resolution, scope.window_date_from, scope.window_date_to)
        raw = report
        collections = [("machine", report.get("machines", [])), ("operator", report.get("operators", []))]
    identities = {}
    for kind, rows in collections:
        keys = {str(row[kind + "_id"]) for row in rows}
        mapping = reader.plans.entities.active_map(kind, sorted(keys))
        if set(mapping) != keys:
            raise WorkbenchCommandRejected("identity_missing", "这张报表里有批次或资源的编号读不到，报表没有生成。请到资料总览核对后再打开。")
        identities[kind] = {key: {"ref": value.ref, "revision": value.revision} for key, value in mapping.items()}
    fingerprint = {"plan_revision": reader.plans.references.read_revision(), "plan": plan, "raw": raw, "identities": identities}
    return {"scope": scope, "plan": plan, "raw": raw, "report": report, "fingerprint": fingerprint, "identities": identities}


def _identity(facts, kind, key):
    return facts["identities"][kind][str(key)]["ref"]


def _overdue_rows(facts, *, as_of: datetime):
    rows, source_rows = [], []
    scheduled, unscheduled, invalid = compute_overdue_bucket_groups(facts["raw"], now_dt=as_of)
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
                public["utilization_percent"] = utilization_percent(row.get("utilization"))
                public["availability_note"] = utilization_availability_note(row)
            rows.append(public)
            source_rows.append({**row, "resource_kind": kind})
    return rows, source_rows


def catalog_workspace(facts, page, *, as_of: datetime):
    scope, rep = facts["scope"], facts["report"]
    rows, source_rows = _overdue_rows(facts, as_of=as_of) if scope.kind == "overdue" else _resource_rows(facts)
    source_by_key = {}
    for public, raw in zip(rows, source_rows):
        source_by_key[public.get("batch_ref") or public["resource_ref"]] = raw
    query = scope.query.strip().casefold()
    columns = [key for key, _ in CATALOG_COLUMNS[scope.kind]]
    # 数值列的 0 / 0.0 是合法值，也要能被搜到；只有缺值才算空。
    rows = [row for row in rows
            if query in " ".join("" if value is None else str(value) for value in (row[key] for key in columns)).casefold()]
    ordered, visible, pagination = page.apply(rows, columns)
    selected = [source_by_key[row.get("batch_ref") or row["resource_ref"]] for row in ordered]
    provenance, gap = CATALOG_CONTEXT[scope.kind]
    data = {"plan": facts["plan"], "scope": scope.scope(), "topic": scope.kind,
            "rows": visible, "columns": [{"key": key, "label": label} for key, label in CATALOG_COLUMNS[scope.kind]],
            "summary": {"rows": len(ordered)}, "page": pagination,
            "provenance": provenance, "data_gaps": [gap]}
    if scope.kind == "utilization":
        data["scope"].update(metric_source=rep["metric_source"], metric_version=rep["metric_version"])
    if rep and rep.get("report_degraded"):
        data["data_gaps"].append("有一部分原始数据不可用，没有参与本表计算，请核对原始记录。")
    return data, ordered, selected


def export_catalog_xlsx(reader, data, selected, snapshot):
    if not selected:
        raise WorkbenchCommandRejected("empty_export", "当前筛选范围里没有可导出的结果，没有开始下载。请放宽筛选条件后重试。", 422)
    decision = ensure_export_size(reader.engine, len(selected))
    kind = data["topic"]
    def render(write_only=False):
        options = {"summary_rows": metadata(data, snapshot), "write_only": write_only}
        if kind == "overdue":
            return export_overdue_xlsx(selected, **options)
        if kind == "downtime":
            return export_downtime_impact_xlsx(selected, **options)
        return export_utilization_xlsx([row for row in selected if row["resource_kind"] == "machine"],
                                      [row for row in selected if row["resource_kind"] == "operator"], **options)
    return reader.engine._build_xlsx_export(filename=TOPIC_TITLES[kind] + ".xlsx",
        decision=decision, build_direct=render, build_stream=lambda: render(True))
