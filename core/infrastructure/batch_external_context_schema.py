"""Frozen external scheduling context belongs to the batch operation, not its template."""

from core.infrastructure.workbench_metadata_schema import canonical_sql


def capture_select(operation_sql, origin):
    """Fixed SQL fragments supplied only by this module and its migration."""
    return """SELECT o.id,b.part_no,o.seq,t.id,t.status,t.ext_group_id,
        g.part_no,g.start_seq,g.end_seq,g.merge_mode,g.total_days,g.supplier_id,r.ref,tr.ref,
        '""" + origin + """',CURRENT_TIMESTAMP
        FROM """ + operation_sql + """ o JOIN Batches b ON b.batch_id=o.batch_id
        LEFT JOIN PartOperations t ON t.part_no=b.part_no AND t.seq=o.seq
        LEFT JOIN ExternalGroups g ON g.group_id=t.ext_group_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='template_operation'
            AND tr.entity_key=CAST(t.id AS TEXT) AND tr.active=1
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group'
            AND r.entity_key=g.group_id AND r.active=1
        WHERE lower(trim(o.source))='external'"""


def objects():
    capture = "INSERT INTO BatchExternalContexts " + capture_select(
        "(SELECT * FROM BatchOperations WHERE id=NEW.id)", "creation") + ";"
    return {
        "BatchExternalContexts": """CREATE TABLE BatchExternalContexts (
            operation_id INTEGER PRIMARY KEY,
            part_no TEXT NOT NULL, sequence INTEGER NOT NULL,
            template_operation_id INTEGER, template_status TEXT,
            group_id TEXT, group_part_no TEXT, start_sequence INTEGER, end_sequence INTEGER,
            merge_mode TEXT, total_days REAL, supplier_id TEXT, group_ref TEXT,
            template_operation_ref TEXT,
            origin TEXT NOT NULL CHECK(origin IN ('creation','template_copy','instance_copy','migration_v33')),
            captured_at TEXT NOT NULL,
            FOREIGN KEY(operation_id) REFERENCES BatchOperations(id) ON DELETE CASCADE)""",
        "batch_external_context_created": """CREATE TRIGGER batch_external_context_created
            AFTER INSERT ON BatchOperations WHEN lower(trim(NEW.source))='external' BEGIN """ + capture + " END",
        "batch_external_context_source_changed": """CREATE TRIGGER batch_external_context_source_changed
            AFTER UPDATE OF source ON BatchOperations WHEN lower(trim(NEW.source))='external'
                AND lower(trim(OLD.source)) IS NOT lower(trim(NEW.source))
            BEGIN DELETE FROM BatchExternalContexts WHERE operation_id=NEW.id; """ + capture + " END",
    }


def contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_batch_external_context:" if name not in actual else "invalid_batch_external_context:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "")]


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Batch external context installation requires a migration transaction.")
    definitions = objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(definitions):
        issues = contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial batch external contexts: " + ";".join(issues))
        return
    for sql in definitions.values():
        conn.execute(sql)
    # This is the context visible at upgrade time, never claimed to be the context at birth.
    conn.execute("INSERT INTO BatchExternalContexts " + capture_select("BatchOperations", "migration_v33"))
