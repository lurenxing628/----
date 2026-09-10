"""Dashboard-only source gaps; keep DI identities and SQLite storage values."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_ROWS, bounded
from data.repositories.workbench_dashboard_source_repo import rows

SOURCE_GAPS = {"identity_missing", "identity_drift", "entity_not_found", "constraint_conflict"}


def latest_fact(reader, ref):
    # Validate raw dates before DI's JSON-only DTO admission rejects a legacy BLOB.
    selected = rows(reader.conn, "SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT 1", (ref,))
    if not selected:
        raise WorkbenchCommandRejected("outsourcing_unavailable", "外协登记缺少确认事实，请恢复完整记录。", 503)
    return selected[0]


def unknown_sources(conn):
    # An invalid source is not proof of an internal operation. Do not hide it.
    return bounded(rows(conn, """SELECT r.ref AS operation_ref, b.ref AS batch_ref,
        m.outsourcing_ref, CASE WHEN 1 THEN o.op_code END AS business_code,
        CASE WHEN 1 THEN o.source END AS source
        FROM BatchOperations o
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
        LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
        LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
        WHERE o.source IS NULL OR o.source NOT IN ('internal','external')
        ORDER BY o.id LIMIT ?""", (MAX_ROWS + 1,)))


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
