"""DT metadata extension for external dashboard items."""

from core.infrastructure.workbench_metadata_schema import canonical_sql

from .schema_structure import schema_objects

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_dashboard_external_objects():
    result = {
        "WorkbenchDashboardExternalItems": """CREATE TABLE WorkbenchDashboardExternalItems (
            item_ref """ + _REF.format("item_ref") + """ PRIMARY KEY,
            category TEXT NOT NULL DEFAULT 'external' CHECK(category='external'),
            outsourcing_ref TEXT NOT NULL UNIQUE,
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref))""",
        "WorkbenchDashboardExternalStates": """CREATE TABLE WorkbenchDashboardExternalStates (
            item_ref TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0),
            handling_json TEXT NOT NULL, origin_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardExternalItems(item_ref))""",
        "WorkbenchDashboardExternalHistory": """CREATE TABLE WorkbenchDashboardExternalHistory (
            history_ref """ + _REF.format("history_ref") + """ PRIMARY KEY, item_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0),
            action TEXT NOT NULL CHECK(action IN ('transition','reopen')), before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            source_json TEXT NOT NULL, source_facts_json TEXT NOT NULL,
            reason TEXT, local_operator TEXT NOT NULL, recorded_at TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(item_ref,sequence), FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardExternalStates(item_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED)""",
        "wb_dashboard_external_receipt_insert": """CREATE TRIGGER wb_dashboard_external_receipt_insert
            AFTER INSERT ON WorkbenchOutsourcingReceipts BEGIN
            INSERT INTO WorkbenchDashboardExternalItems(item_ref,outsourcing_ref)
                VALUES(lower(hex(randomblob(24))),NEW.outsourcing_ref); END""",
        "wb_dashboard_external_state_identity": """CREATE TRIGGER wb_dashboard_external_state_identity
            BEFORE UPDATE ON WorkbenchDashboardExternalStates
            WHEN NEW.item_ref IS NOT OLD.item_ref OR NEW.origin_json IS NOT OLD.origin_json OR NEW.revision<>OLD.revision+1
            BEGIN SELECT RAISE(ABORT,'dashboard origin is permanent'); END""",
    }
    conflicts = {"Items": "item_ref=NEW.item_ref OR outsourcing_ref=NEW.outsourcing_ref",
                 "States": "item_ref=NEW.item_ref",
                 "History": "history_ref=NEW.history_ref OR request_key=NEW.request_key OR (item_ref=NEW.item_ref AND sequence=NEW.sequence)"}
    for suffix, condition in conflicts.items():
        table = "WorkbenchDashboardExternal" + suffix
        for event in (("DELETE",) if suffix == "States" else ("UPDATE", "DELETE")):
            name = "wb_dashboard_external_" + suffix.lower() + "_no_" + event.lower()
            result[name] = f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END"
        name = "wb_dashboard_external_" + suffix.lower() + "_no_replace"
        result[name] = (f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                        "BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END")
    return result


def workbench_dashboard_external_contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return [("missing_dashboard_external_schema:" if name not in actual else "invalid_dashboard_external_schema:") + name
            for name, sql in workbench_dashboard_external_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
