"""DI integration DDL. Explicit caller transaction; no version change or auto repair.

Call install(conn) in the coordinator's migration, then register the route hook.
objects() is the exact ordered DDL; contract_issues() is a SELECT-only check.
Existing operations use retained birth evidence; missing birth stays unknown.
New operations capture their batch instance on insert, never a template group.
"""

from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.infrastructure.workbench_template_lineage_schema import template_lineage_contract_issues

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_outsourcing_objects():
    objects = {
        "WorkbenchOutsourcingOperationOrigins": """CREATE TABLE WorkbenchOutsourcingOperationOrigins (
            operation_ref TEXT PRIMARY KEY NOT NULL, batch_ref TEXT,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref))""",
        "WorkbenchOutsourcingReceipts": """CREATE TABLE WorkbenchOutsourcingReceipts (
            outsourcing_ref """ + _REF.format("outsourcing_ref") + """ PRIMARY KEY,
            target_kind TEXT NOT NULL CHECK(target_kind IN ('single','merged')),
            batch_ref TEXT NOT NULL, supplier_ref TEXT NOT NULL,
            origin_json TEXT NOT NULL, identity_json TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(supplier_ref) REFERENCES WorkbenchEntityRefs(ref))""",
        "WorkbenchOutsourcingMembers": """CREATE TABLE WorkbenchOutsourcingMembers (
            operation_ref TEXT PRIMARY KEY NOT NULL, outsourcing_ref TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchOutsourcingOperationOrigins(operation_ref),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref))""",
        "idx_wb_outsourcing_members_receipt": "CREATE INDEX idx_wb_outsourcing_members_receipt ON WorkbenchOutsourcingMembers(outsourcing_ref)",
        "WorkbenchOutsourcingFacts": """CREATE TABLE WorkbenchOutsourcingFacts (
            fact_ref """ + _REF.format("fact_ref") + """ PRIMARY KEY, outsourcing_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0), previous_fact_ref TEXT,
            sent TEXT NOT NULL, planned TEXT NOT NULL, returned TEXT,
            confirmed_state TEXT NOT NULL CHECK(confirmed_state IN ('in_transit','returned','awaiting_confirmation')),
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator))>0),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator))>0),
            reason TEXT NOT NULL CHECK(length(trim(reason))>0), recorded_at TEXT NOT NULL,
            before_json TEXT NOT NULL, source_facts_json TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(outsourcing_ref,sequence), UNIQUE(previous_fact_ref),
            CHECK(planned>=sent AND (returned IS NULL OR returned>=sent)),
            CHECK(sent<=recorded_at AND (returned IS NULL OR returned<=recorded_at)),
            CHECK((confirmed_state='returned')=(returned IS NOT NULL)),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref),
            FOREIGN KEY(previous_fact_ref) REFERENCES WorkbenchOutsourcingFacts(fact_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED)""",
        "wb_outsourcing_operation_born": """CREATE TRIGGER wb_outsourcing_operation_born AFTER INSERT ON WorkbenchPlanSourceRefs
            WHEN NEW.kind='operation' AND NEW.active=1 BEGIN
            INSERT INTO WorkbenchOutsourcingOperationOrigins(operation_ref,batch_ref)
            SELECT NEW.ref,(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=o.batch_id)
            FROM BatchOperations o WHERE CAST(o.id AS TEXT)=NEW.source_key; END""",
        "wb_outsourcing_fact_sequence": """CREATE TRIGGER wb_outsourcing_fact_sequence BEFORE INSERT ON WorkbenchOutsourcingFacts BEGIN
            SELECT CASE WHEN NEW.sequence<>COALESCE((SELECT MAX(sequence) FROM WorkbenchOutsourcingFacts
                WHERE outsourcing_ref=NEW.outsourcing_ref),0)+1 OR NEW.previous_fact_ref IS NOT
                (SELECT fact_ref FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=NEW.outsourcing_ref ORDER BY sequence DESC LIMIT 1)
                THEN RAISE(ABORT,'outsourcing fact sequence mismatch') END;
            SELECT CASE WHEN (SELECT COUNT(*) FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=NEW.outsourcing_ref)<
                (SELECT CASE target_kind WHEN 'single' THEN 1 ELSE 2 END FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=NEW.outsourcing_ref)
                THEN RAISE(ABORT,'outsourcing members incomplete') END; END""",
        "wb_outsourcing_members_sealed": """CREATE TRIGGER wb_outsourcing_members_sealed BEFORE INSERT ON WorkbenchOutsourcingMembers
            WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=NEW.outsourcing_ref)
              OR EXISTS(SELECT 1 FROM WorkbenchOutsourcingReceipts r JOIN WorkbenchOutsourcingMembers m
                  ON m.outsourcing_ref=r.outsourcing_ref WHERE r.outsourcing_ref=NEW.outsourcing_ref AND r.target_kind='single')
            BEGIN SELECT RAISE(ABORT,'outsourcing membership is sealed'); END""",
    }
    conflicts = {"OperationOrigins": "operation_ref=NEW.operation_ref", "Receipts": "outsourcing_ref=NEW.outsourcing_ref",
                 "Members": "operation_ref=NEW.operation_ref", "Facts": "fact_ref=NEW.fact_ref OR request_key=NEW.request_key OR (outsourcing_ref=NEW.outsourcing_ref AND sequence=NEW.sequence)"}
    for suffix, condition in conflicts.items():
        table = "WorkbenchOutsourcing" + suffix
        for event in ("UPDATE", "DELETE"):
            name = "wb_outsourcing_" + suffix.lower() + "_no_" + event.lower()
            objects[name] = "CREATE TRIGGER " + name + " BEFORE " + event + " ON " + table + " BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END"
        name = "wb_outsourcing_" + suffix.lower() + "_no_replace"
        objects[name] = ("CREATE TRIGGER " + name + " BEFORE INSERT ON " + table + " WHEN EXISTS(SELECT 1 FROM " +
                         table + " WHERE " + condition + ") BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END")
    return objects


def workbench_outsourcing_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_outsourcing_schema:" if name not in actual else "invalid_outsourcing_schema:") + name
            for name, sql in workbench_outsourcing_objects().items()
            if name not in actual or _canonical_sql(sql) != _canonical_sql(actual[name] or "")]


def install_workbench_outsourcing_schema(conn):
    if not conn.in_transaction:
        raise RuntimeError("Outsourcing installation requires the caller's migration transaction")
    definitions = workbench_outsourcing_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    issues = (workbench_metadata_contract_issues(conn) + workbench_plan_identity_contract_issues(conn) +
              template_lineage_contract_issues(conn))
    if names & set(definitions):
        issues += workbench_outsourcing_contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot install or repair outsourcing schema: " + ";".join(issues))
    if names & set(definitions):
        if conn.execute("SELECT 1 FROM WorkbenchPlanSourceRefs r WHERE r.kind='operation' AND r.active=1 "
                        "AND NOT EXISTS(SELECT 1 FROM WorkbenchOutsourcingOperationOrigins o WHERE o.operation_ref=r.ref) LIMIT 1").fetchone():
            raise RuntimeError("Outsourcing origins are missing; existing installation cannot be repaired")
        return
    if conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action='outsourcing.confirm' LIMIT 1").fetchone():
        raise RuntimeError("Outsourcing receipts exist without facts; restore a complete backup")
    if conn.execute("SELECT 1 FROM BatchOperations o WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs r "
                    "WHERE r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)) LIMIT 1").fetchone():
        raise RuntimeError("Outsourcing operation identities are missing; no guessed replacements")
    for sql in definitions.values():
        conn.execute(sql)
    # No birth evidence means unknown, not permission to attach to a same-number batch.
    conn.execute("""INSERT INTO WorkbenchOutsourcingOperationOrigins(operation_ref,batch_ref)
        SELECT r.ref,(SELECT e.batch_ref FROM WorkbenchTemplateLineageEvents e
            WHERE e.operation_ref=r.ref AND e.event_type='created' ORDER BY e.event_id LIMIT 1)
        FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o ON r.source_key=CAST(o.id AS TEXT)
        WHERE r.kind='operation' AND r.active=1""")


objects = workbench_outsourcing_objects
contract_issues = workbench_outsourcing_contract_issues
install = install_workbench_outsourcing_schema
