"""Workbench dashboard schema and contract validation."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import (
    DASHBOARD_HANDLING_ACTION_VALUES,
    DASHBOARD_ITEM_CATEGORY_VALUES,
    DashboardItemCategory,
    enum_check,
    enum_predicate,
    flag_check,
)

from .schema_structure import SchemaStructure

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_dashboard_objects():
    result = {
        "WorkbenchDashboardItems": """CREATE TABLE WorkbenchDashboardItems (
            item_ref {} PRIMARY KEY,
            category TEXT NOT NULL {category},
            batch_ref TEXT,
            task_ref TEXT CHECK(task_ref IS NULL OR (length(task_ref)=48 AND task_ref NOT GLOB '*[^0-9a-f]*')),
            outsourcing_ref TEXT,
            CHECK(({batch_items} AND batch_ref IS NOT NULL AND task_ref IS NULL AND outsourcing_ref IS NULL)
               OR ({task_items} AND task_ref IS NOT NULL AND batch_ref IS NULL AND outsourcing_ref IS NULL)
               OR (category='{external}' AND outsourcing_ref IS NOT NULL AND batch_ref IS NULL AND task_ref IS NULL)),
            UNIQUE(category,batch_ref), UNIQUE(category,task_ref), UNIQUE(outsourcing_ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref)
        )""".format(
            _REF.format("item_ref"), category=enum_check("category", DASHBOARD_ITEM_CATEGORY_VALUES),
            batch_items=enum_predicate("category", (DashboardItemCategory.DELIVERY.value, DashboardItemCategory.MATERIAL.value)),
            task_items=enum_predicate("category", (DashboardItemCategory.ACTUAL.value, DashboardItemCategory.DOWNTIME.value)),
            external=DashboardItemCategory.EXTERNAL.value),
        "WorkbenchDashboardStates": """CREATE TABLE WorkbenchDashboardStates (
            item_ref TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0),
            handling_json TEXT NOT NULL, origin_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardItems(item_ref)
        )""",
        "WorkbenchDashboardHistory": """CREATE TABLE WorkbenchDashboardHistory (
            history_ref {} PRIMARY KEY, item_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0),
            action TEXT NOT NULL {action}, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            source_json TEXT NOT NULL,
            reason TEXT, local_operator TEXT NOT NULL, recorded_at TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(item_ref,sequence), FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardStates(item_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("history_ref"), action=enum_check("action", DASHBOARD_HANDLING_ACTION_VALUES)),
        "WorkbenchDashboardDowntimeRefs": f"""CREATE TABLE WorkbenchDashboardDowntimeRefs (
            ref {_REF.format('ref')} PRIMARY KEY, source_id INTEGER NOT NULL, active INTEGER NOT NULL {flag_check('active')},
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0)
        )""",
        "idx_wb_dashboard_downtime_active": "CREATE UNIQUE INDEX idx_wb_dashboard_downtime_active ON WorkbenchDashboardDowntimeRefs(source_id) WHERE active=1",
        "wb_dashboard_batch_insert": f"""CREATE TRIGGER wb_dashboard_batch_insert AFTER INSERT ON WorkbenchEntityRefs
            WHEN NEW.kind='batch' AND NEW.active=1 BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'{DashboardItemCategory.DELIVERY.value}',NEW.ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'{DashboardItemCategory.MATERIAL.value}',NEW.ref); END""",
        "wb_dashboard_task_insert": f"""CREATE TRIGGER wb_dashboard_task_insert AFTER INSERT ON Schedule BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'{DashboardItemCategory.ACTUAL.value}',NEW.task_ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'{DashboardItemCategory.DOWNTIME.value}',NEW.task_ref); END""",
        "wb_dashboard_external_receipt_insert": f"""CREATE TRIGGER wb_dashboard_external_receipt_insert AFTER INSERT ON WorkbenchOutsourcingReceipts BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,outsourcing_ref) VALUES(lower(hex(randomblob(24))),'{DashboardItemCategory.EXTERNAL.value}',NEW.outsourcing_ref); END""",
        "wb_dashboard_downtime_insert": """CREATE TRIGGER wb_dashboard_downtime_insert AFTER INSERT ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET active=0,revision=revision+1 WHERE source_id=NEW.id AND active=1;
            INSERT INTO WorkbenchDashboardDowntimeRefs(ref,source_id,active,revision)
            VALUES(lower(hex(randomblob(24))),NEW.id,1,1); END""",
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
        "Items": "item_ref=NEW.item_ref OR (category=NEW.category AND batch_ref=NEW.batch_ref) OR (category=NEW.category AND task_ref=NEW.task_ref) OR outsourcing_ref=NEW.outsourcing_ref",
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


def workbench_dashboard_contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_dashboard_schema:" if name not in actual else "invalid_dashboard_schema:") + name
            for name, sql in workbench_dashboard_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
