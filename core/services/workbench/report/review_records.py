"""Render ledger reports without reinterpreting completion."""


def resource_directory(facts):
    return _resource_directory(facts["resources"], facts["ledger"]["resources"])


def choice_directory(resources, actual_resources):
    return {**_resource_directory(resources, actual_resources), "batch": resources["batch"]}


def _resource_directory(resources, actual_resources):
    result = {}
    for kind, collection in (("machine", "machines"), ("operator", "operators")):
        result[kind] = {row["ref"]: row for row in resources[kind].values()}
        result[kind].update((row["ref"], {key: row[key] for key in ("ref", "label", "available")})
                            for row in actual_resources[collection])
    return result


def actual_resource(directory, kind, ref):
    if ref is None:
        return {"ref": None, "label": "未填写", "available": False}
    return directory[kind].get(ref, {"ref": ref, "label": "原资源资料不可用", "available": False})


def project_records(projection, operation, directory):
    common = {key: operation[key] for key in ("operation_ref", "batch_ref", "batch_label", "operation_label", "operation_source")}
    records = []
    incomplete_reports = {gap.get("report_ref") for gap in projection["data_gaps"] if gap.get("report_ref")}
    for report in projection["reports"]:
        public = {key: value for key, value in report.items() if key != "write_context"}
        records.append({**public, **common, "projection_index": len(records), "record_kind": "production_report",
            "record_kind_label": "逐次报工", "event_time": report["actual_end"] or report["actual_start"],
            "recorded_at_time_basis": "factory_local",
            "data_quality": "incomplete" if report["report_ref"] in incomplete_reports else "complete"})
    for row in records:
        for kind in ("machine", "operator"):
            resource = actual_resource(directory, kind, row["actual_" + kind + "_ref"])
            row.update({kind + "_ref": resource["ref"], kind + "_label": resource["label"],
                        kind + "_available": resource.get("available", True)})
    return records
