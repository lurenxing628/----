"""Explicit metadata-only installation. The main migration owns version changes."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_dashboard_objects():
    result = {
        "WorkbenchDashboardItems": """CREATE TABLE WorkbenchDashboardItems (
            item_ref {} PRIMARY KEY, category TEXT NOT NULL CHECK(category IN ('delivery','material','actual','downtime')),
            batch_ref TEXT, task_ref TEXT,
            CHECK((category IN ('delivery','material') AND batch_ref IS NOT NULL AND task_ref IS NULL)
               OR (category IN ('actual','downtime') AND task_ref IS NOT NULL AND batch_ref IS NULL)),
            UNIQUE(category,batch_ref), UNIQUE(category,task_ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(task_ref) REFERENCES WorkbenchTaskRefs(ref)
        )""".format(_REF.format("item_ref")),
        "WorkbenchDashboardStates": """CREATE TABLE WorkbenchDashboardStates (
            item_ref TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0),
            handling_json TEXT NOT NULL, origin_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardItems(item_ref)
        )""",
        "WorkbenchDashboardHistory": """CREATE TABLE WorkbenchDashboardHistory (
            history_ref {} PRIMARY KEY, item_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0),
            action TEXT NOT NULL CHECK(action IN ('transition','reopen')), before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            source_json TEXT NOT NULL, source_facts_json TEXT NOT NULL, source_hash TEXT NOT NULL,
            reason TEXT, local_operator TEXT NOT NULL, recorded_at TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(item_ref,sequence), FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardStates(item_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("history_ref")),
        "WorkbenchDashboardDowntimeRefs": """CREATE TABLE WorkbenchDashboardDowntimeRefs (
            ref {} PRIMARY KEY, source_id INTEGER NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0)
        )""".format(_REF.format("ref")),
        "idx_wb_dashboard_downtime_active": "CREATE UNIQUE INDEX idx_wb_dashboard_downtime_active ON WorkbenchDashboardDowntimeRefs(source_id) WHERE active=1",
        "wb_dashboard_batch_insert": """CREATE TRIGGER wb_dashboard_batch_insert AFTER INSERT ON WorkbenchEntityRefs
            WHEN NEW.kind='batch' AND NEW.active=1 BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'delivery',NEW.ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'material',NEW.ref); END""",
        "wb_dashboard_task_insert": """CREATE TRIGGER wb_dashboard_task_insert AFTER INSERT ON WorkbenchTaskRefs BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'actual',NEW.ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'downtime',NEW.ref); END""",
        "wb_dashboard_downtime_insert": """CREATE TRIGGER wb_dashboard_downtime_insert AFTER INSERT ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET active=0,revision=revision+1 WHERE source_id=NEW.id AND active=1;
            INSERT INTO WorkbenchDashboardDowntimeRefs VALUES(lower(hex(randomblob(24))),NEW.id,1,1); END""",
        "wb_dashboard_downtime_update": """CREATE TRIGGER wb_dashboard_downtime_update AFTER UPDATE ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET source_id=NEW.id,revision=revision+1 WHERE source_id=OLD.id AND active=1; END""",
        "wb_dashboard_downtime_delete": """CREATE TRIGGER wb_dashboard_downtime_delete AFTER DELETE ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET active=0,revision=revision+1 WHERE source_id=OLD.id AND active=1; END""",
        "wb_dashboard_state_identity": """CREATE TRIGGER wb_dashboard_state_identity BEFORE UPDATE ON WorkbenchDashboardStates
            WHEN NEW.item_ref IS NOT OLD.item_ref OR NEW.origin_json IS NOT OLD.origin_json OR NEW.revision<>OLD.revision+1
            BEGIN SELECT RAISE(ABORT,'dashboard origin is permanent'); END""",
    }
    for table, events in (("WorkbenchDashboardItems", ("UPDATE", "DELETE")),
                          ("WorkbenchDashboardHistory", ("UPDATE", "DELETE")),
                          ("WorkbenchDashboardStates", ("DELETE",)),
                          ("WorkbenchDashboardDowntimeRefs", ("DELETE",))):
        for event in events:
            name = "wb_dashboard_" + table[18:].lower() + "_no_" + event.lower()
            result[name] = f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END"
    conflicts = {
        "Items": "item_ref=NEW.item_ref OR (category=NEW.category AND batch_ref=NEW.batch_ref) OR (category=NEW.category AND task_ref=NEW.task_ref)",
        "States": "item_ref=NEW.item_ref",
        "History": "history_ref=NEW.history_ref OR request_key=NEW.request_key OR (item_ref=NEW.item_ref AND sequence=NEW.sequence)",
        "DowntimeRefs": "ref=NEW.ref OR (active=1 AND NEW.active=1 AND source_id=NEW.source_id)",
    }
    # SQLite REPLACE can bypass DELETE triggers when recursive_triggers is off.
    for suffix, condition in conflicts.items():
        table, name = "WorkbenchDashboard" + suffix, "wb_dashboard_" + suffix.lower() + "_no_replace"
        result[name] = (f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS "
                        f"(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END")
    return result


def workbench_dashboard_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_dashboard_schema:" if name not in actual else "invalid_dashboard_schema:") + name
            for name, sql in workbench_dashboard_objects().items()
            if name not in actual or _canonical_sql(sql) != _canonical_sql(actual[name] or "")]


def install_workbench_dashboard_schema(conn):
    if not conn.in_transaction:
        raise RuntimeError("Dashboard installation requires the caller's migration transaction")
    definitions = workbench_dashboard_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(definitions):
        issues = workbench_dashboard_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial dashboard schema: " + ";".join(issues))
        return
    issues = workbench_metadata_contract_issues(conn) + workbench_plan_identity_contract_issues(conn)
    if issues or "MachineDowntimes" not in names:
        raise RuntimeError("Dashboard prerequisites are incomplete: " + ";".join(issues))
    if conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action IN ('dashboard.transition','dashboard.reopen') LIMIT 1").fetchone():
        raise RuntimeError("Dashboard receipts exist without their ledger; restore a complete backup")
    for sql in definitions.values():
        conn.execute(sql)
    for category in ("delivery", "material"):
        conn.execute("INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) "
                     "SELECT lower(hex(randomblob(24))),?,ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1", (category,))
    for category in ("actual", "downtime"):
        conn.execute("INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) "
                     "SELECT lower(hex(randomblob(24))),?,ref FROM WorkbenchTaskRefs", (category,))
    conn.execute("INSERT INTO WorkbenchDashboardDowntimeRefs SELECT lower(hex(randomblob(24))),id,1,1 FROM MachineDowntimes")


objects = workbench_dashboard_objects
contract_issues = workbench_dashboard_contract_issues
install = install_workbench_dashboard_schema
