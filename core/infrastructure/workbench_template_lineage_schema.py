"""Caller-owned installation, immutable origins and lossless instance transitions."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.models.workbench_template_lineage import OPERATION_COLUMNS, SEMANTIC_COLUMNS, STATE_COLUMNS

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"
_STAMP = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"


def _state_values(prefix, *, batch="b"):
    values = [prefix + "." + key for key in OPERATION_COLUMNS]
    values += ["(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=" + batch + ".batch_id)",
               "(SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND active=1 AND entity_key=" + batch + ".part_no)",
               batch + ".quantity"]
    return ",".join(values)


def _event_sql(ref, event, changed, prefix, sources, condition="1"):
    return ("INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration," +
            ",".join(STATE_COLUMNS) + ") SELECT " + ref + ",'" + event + "'," + changed + "," +
            _state_values(prefix) + " FROM " + sources + " WHERE " + condition + ";")


def _source_triggers():
    current_ref = "(SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND source_key=CAST(OLD.id AS TEXT))"
    different = " OR ".join("OLD." + key + " IS NOT NEW." + key for key in OPERATION_COLUMNS)
    changed = " OR ".join("OLD." + key + " IS NOT NEW." + key for key in SEMANTIC_COLUMNS + ("batch_id",))
    body = _event_sql(current_ref, "updated", "(" + changed + ")", "NEW", "Batches b",
                      "b.batch_id=NEW.batch_id AND " + current_ref + " IS NOT NULL")
    born = _event_sql("NEW.ref", "created", "0", "o", "BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id",
                      "CAST(o.id AS TEXT)=NEW.source_key")
    # Reference retirement also covers INSERT OR REPLACE with recursive_triggers OFF.
    retired = ("INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration," +
               ",".join(STATE_COLUMNS) + ") SELECT OLD.ref,'retired',1," + ",".join(STATE_COLUMNS) +
               " FROM WorkbenchTemplateLineageEvents WHERE operation_ref=OLD.ref ORDER BY event_id DESC LIMIT 1;")
    batch = _event_sql("r.ref", "batch_changed", "1", "o",
                       "BatchOperations o JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 "
                       "AND r.source_key=CAST(o.id AS TEXT) JOIN Batches b ON b.batch_id=o.batch_id",
                       "o.batch_id=NEW.batch_id")
    return {
        "wb_lineage_operation_born": "CREATE TRIGGER wb_lineage_operation_born AFTER INSERT ON WorkbenchPlanSourceRefs "
            "WHEN NEW.kind='operation' AND NEW.active=1 BEGIN " + born + " END",
        "wb_lineage_operation_update": "CREATE TRIGGER wb_lineage_operation_update BEFORE UPDATE ON BatchOperations "
            "WHEN " + different + " BEGIN " + body + " END",
        "wb_lineage_operation_retire": "CREATE TRIGGER wb_lineage_operation_retire AFTER UPDATE ON WorkbenchPlanSourceRefs "
            "WHEN OLD.kind='operation' AND OLD.active=1 AND NEW.active=0 BEGIN " + retired + " END",
        "wb_lineage_batch_change": "CREATE TRIGGER wb_lineage_batch_change AFTER UPDATE ON Batches "
            "WHEN OLD.part_no IS NOT NEW.part_no OR OLD.quantity IS NOT NEW.quantity BEGIN " + batch + " END",
    }


def template_lineage_objects():
    objects = {
        "WorkbenchTemplateLineageOrigins": """CREATE TABLE WorkbenchTemplateLineageOrigins (
            lineage_ref """ + _REF.format("lineage_ref") + """ PRIMARY KEY,
            operation_ref TEXT NOT NULL UNIQUE, template_operation_ref TEXT NOT NULL,
            template_revision INTEGER NOT NULL CHECK(typeof(template_revision)='integer' AND template_revision>0),
            source_operation_ref TEXT, source_lineage_ref TEXT, source_event_id INTEGER,
            source_eligible INTEGER NOT NULL CHECK(source_eligible IN (0,1)), birth_event_id INTEGER NOT NULL UNIQUE,
            evidence_version TEXT NOT NULL CHECK(evidence_version='template-copy-v1'),
            template_snapshot TEXT NOT NULL, template_fingerprint TEXT NOT NULL,
            instance_snapshot TEXT NOT NULL, instance_fingerprint TEXT NOT NULL,
            recorded_at_utc TEXT NOT NULL DEFAULT (""" + _STAMP + """),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(template_operation_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(source_operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(source_lineage_ref) REFERENCES WorkbenchTemplateLineageOrigins(lineage_ref),
            FOREIGN KEY(birth_event_id) REFERENCES WorkbenchTemplateLineageEvents(event_id),
            CHECK((source_operation_ref IS NULL)=(source_lineage_ref IS NULL)),
            CHECK((source_operation_ref IS NULL)=(source_event_id IS NULL)),
            CHECK(source_operation_ref IS NOT NULL OR source_eligible=1)
        )""",
        "WorkbenchTemplateLineageEvents": """CREATE TABLE WorkbenchTemplateLineageEvents (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_ref TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN ('created','updated','retired','batch_changed','withdrawn')),
            affects_calibration INTEGER NOT NULL CHECK(affects_calibration IN (0,1)),
            reason TEXT, recorded_at_utc TEXT NOT NULL DEFAULT (""" + _STAMP + "),\n" +
            ",".join(STATE_COLUMNS) + ", FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref))",
        "idx_wb_lineage_events_operation": "CREATE INDEX idx_wb_lineage_events_operation ON WorkbenchTemplateLineageEvents(operation_ref,event_id)",
        "idx_wb_lineage_birth": "CREATE UNIQUE INDEX idx_wb_lineage_birth ON WorkbenchTemplateLineageEvents(operation_ref) WHERE event_type='created'",
        "idx_wb_lineage_template_revision": "CREATE INDEX idx_wb_lineage_template_revision ON WorkbenchTemplateLineageOrigins(template_operation_ref,template_revision)",
    }
    objects.update(_source_triggers())
    for table, stem in (("WorkbenchTemplateLineageOrigins", "origin"), ("WorkbenchTemplateLineageEvents", "event")):
        for event in ("update", "delete"):
            name = "wb_lineage_" + stem + "_no_" + event
            objects[name] = ("CREATE TRIGGER " + name + " BEFORE " + event.upper() + " ON " + table +
                             " BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END")
    objects["wb_lineage_origin_birth"] = """CREATE TRIGGER wb_lineage_origin_birth BEFORE INSERT ON WorkbenchTemplateLineageOrigins BEGIN
        SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM WorkbenchTemplateLineageEvents e
            JOIN WorkbenchPlanSourceRefs r ON r.ref=e.operation_ref AND r.kind='operation' AND r.active=1
            WHERE e.event_id=NEW.birth_event_id AND e.operation_ref=NEW.operation_ref AND e.event_type='created')
            THEN RAISE(ABORT,'template lineage requires a new instance birth') END;
        SELECT CASE WHEN EXISTS (SELECT 1 FROM WorkbenchTemplateLineageOrigins WHERE operation_ref=NEW.operation_ref OR lineage_ref=NEW.lineage_ref)
            THEN RAISE(ABORT,'template lineage cannot be rebound') END;
    END"""
    objects["wb_lineage_event_no_replace"] = """CREATE TRIGGER wb_lineage_event_no_replace BEFORE INSERT ON WorkbenchTemplateLineageEvents
        WHEN EXISTS (SELECT 1 FROM WorkbenchTemplateLineageEvents WHERE event_id=NEW.event_id)
        BEGIN SELECT RAISE(ABORT,'template lineage events cannot be replaced'); END"""
    return objects


def template_lineage_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_template_lineage:" if name not in actual else "invalid_template_lineage:") + name
            for name, sql in template_lineage_objects().items()
            if name not in actual or _canonical_sql(actual[name] or "") != _canonical_sql(sql)]


def _source_contract_issues(conn):
    required = {"BatchOperations": set(OPERATION_COLUMNS), "Batches": {"batch_id", "part_no", "quantity"},
                "PartOperations": {"id", "part_no", "seq", "op_type_id", "op_type_name", "source", "supplier_id",
                                   "setup_hours", "unit_hours", "ext_days", "ext_group_id", "status", "created_at"}}
    return ["missing_template_lineage_source:" + table + "." + column for table, columns in required.items()
            for column in sorted(columns - {row[1] for row in conn.execute('PRAGMA table_info("' + table + '")')})]


def install_template_lineage(conn):
    """Never backfill, commit, alter a business table, or repair a partial install."""
    if not conn.in_transaction:
        raise RuntimeError("install_template_lineage requires the caller's migration transaction.")
    objects = template_lineage_objects()
    actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    issues = (workbench_metadata_contract_issues(conn) + workbench_process_contract_issues(conn) +
              workbench_plan_identity_contract_issues(conn) + _source_contract_issues(conn))
    if actual & set(objects):
        issues += template_lineage_contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot install template lineage: " + "; ".join(issues))
    if not actual & set(objects):
        for sql in objects.values():
            conn.execute(sql)


objects = template_lineage_objects
contract_issues = template_lineage_contract_issues
install = install_template_lineage
