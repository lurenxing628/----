"""Render ledger reports and preserved events without reinterpreting completion."""

from .review_values import local_time

EVENT_LABELS = {"start": "开工", "finish": "整道完工", "pause": "暂停", "resume": "恢复", "exception": "异常"}


def resource_directory(facts):
    result = {}
    for kind, collection in (("machine", "machines"), ("operator", "operators")):
        result[kind] = {row["ref"]: row for row in facts["resources"][kind].values()}
        result[kind].update((row["ref"], {key: row[key] for key in ("ref", "label", "available")})
                            for row in facts["ledger"]["resources"][collection])
    return result


def actual_resource(directory, kind, ref):
    if ref is None:
        return {"ref": None, "label": "未填写", "available": False}
    return directory[kind].get(ref, {"ref": ref, "label": "原资源资料不可用", "available": False})


def project_records(projection, operation, directory, as_of):
    common = {key: operation[key] for key in ("operation_ref", "batch_ref", "batch_label", "operation_label")}
    records = []
    incomplete_reports = {gap.get("report_ref") for gap in projection["data_gaps"] if gap.get("report_ref")}
    for index, event in enumerate(projection["legacy_facts"]):
        time = local_time(event["event_time"])
        records.append({**event, **common, "projection_index": index, "record_kind": "legacy_event",
            "record_kind_label": "现场事件", "report_ref": None, "report_no": None,
            "event_label": EVENT_LABELS.get(event["event_type"], "执行事件"), "event_time": time,
            "event_time_raw": event["event_time"], "event_time_basis": "factory_local",
            "recorded_at": event["created_at"], "recorded_at_time_basis": event["created_at_time_basis"],
            "actual_start": None, "actual_end": None, "revision_ref": None, "correction_history": [],
            "legacy_evidence": event,
            "data_quality": "invalid" if time is None or time > as_of else "legacy_incomplete"})
    for report in projection["reports"]:
        public = {key: value for key, value in report.items() if key != "write_context"}
        records.append({**public, **common, "projection_index": len(records), "record_kind": "production_report",
            "record_kind_label": "逐次报工", "event_type": "production_report", "event_label": "逐次报工",
            "event_time": report["actual_end"] or report["actual_start"], "event_time_basis": "factory_local",
            "recorded_at_time_basis": "factory_local", "quantity_done": report["completed_quantity"],
            "quantity_scrapped": None, "data_quality": "incomplete" if report["report_ref"] in incomplete_reports else "complete"})
    for row in records:
        for kind in ("machine", "operator"):
            resource = actual_resource(directory, kind, row["actual_" + kind + "_ref"])
            row.update({kind + "_ref": resource["ref"], kind + "_label": resource["label"],
                        kind + "_available": resource.get("available", True)})
    return records
