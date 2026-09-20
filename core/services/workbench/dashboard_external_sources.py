"""Dashboard-only source gaps; keep DI identities and SQLite storage values."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_ROWS, bounded
from data.repositories.workbench_dashboard_source_repo import latest_outsourcing_fact_rows, unknown_source_rows

SOURCE_GAPS = {"identity_missing", "identity_drift", "entity_not_found", "constraint_conflict"}


def latest_fact(reader, ref):
    # Validate raw dates before DI's JSON-only DTO admission rejects a legacy BLOB.
    selected = latest_outsourcing_fact_rows(reader.conn, ref)
    if not selected:
        raise WorkbenchCommandRejected("outsourcing_unavailable", "这条外协登记缺少确认记录，请先恢复完整记录。", 503)
    return selected[0]


def unknown_sources(conn):
    # An invalid source is not proof of an internal operation. Do not hide it.
    return bounded(unknown_source_rows(conn, MAX_ROWS + 1))


def target_source(reader, item):
    if item["issues"]:
        return None, item["issues"]
    target = {"kind": "single", "batch_ref": item["batch_ref"], "supplier_ref": item["supplier_ref"],
              "operation_refs": [item["operation_ref"]]}
    try:
        return reader.sources.load(target), []
    except WorkbenchCommandRejected as exc:
        if exc.code not in SOURCE_GAPS:
            raise
        return None, [{"code": exc.code, "message": str(exc)}]


def subject(value, fallback):
    return value if type(value) is str and value.strip() else fallback


def gap(ref, title, issues):
    return {"source_ref": ref, "subject": title, "code": issues[0]["code"],
            "message": "；".join(issue["message"] for issue in issues)}
