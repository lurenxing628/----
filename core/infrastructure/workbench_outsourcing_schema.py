"""Workbench outsourcing schema and contract validation."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import (
    OUTSOURCING_CONFIRMED_STATE_VALUES,
    OUTSOURCING_TARGET_KIND_VALUES,
    OutsourcingConfirmedState,
    enum_check,
)

from .schema_structure import SchemaStructure

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"
_CONFIRMED_STATE = enum_check("confirmed_state", OUTSOURCING_CONFIRMED_STATE_VALUES)


def workbench_outsourcing_objects():
    objects = {
        "WorkbenchOutsourcingReceipts": """CREATE TABLE WorkbenchOutsourcingReceipts (
            outsourcing_ref """ + _REF.format("outsourcing_ref") + """ PRIMARY KEY,
            target_kind TEXT NOT NULL """ + enum_check("target_kind", OUTSOURCING_TARGET_KIND_VALUES) + """,
            batch_ref TEXT NOT NULL, supplier_ref TEXT NOT NULL,
            origin_json TEXT NOT NULL, identity_json TEXT NOT NULL, created_at TEXT NOT NULL,
            latest_fact_ref """ + _REF.format("latest_fact_ref") + """,
            history_count INTEGER NOT NULL CHECK(typeof(history_count)='integer' AND history_count>0),
            sent TEXT NOT NULL, planned TEXT NOT NULL, returned TEXT,
            confirmed_state TEXT NOT NULL """ + _CONFIRMED_STATE + """,
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator))>0),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator))>0),
            reason TEXT NOT NULL CHECK(length(trim(reason))>0),
            recorded_at TEXT NOT NULL,
            CHECK(planned>=sent AND (returned IS NULL OR returned>=sent)),
            CHECK(sent<=recorded_at AND (returned IS NULL OR returned<=recorded_at)),
            CHECK((confirmed_state='""" + OutsourcingConfirmedState.RETURNED.value + """')=(returned IS NOT NULL)),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(supplier_ref) REFERENCES WorkbenchEntityRefs(ref)
        )""",
        "WorkbenchOutsourcingMembers": """CREATE TABLE WorkbenchOutsourcingMembers (
            operation_ref TEXT PRIMARY KEY NOT NULL, outsourcing_ref TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref))""",
        "idx_wb_outsourcing_members_receipt": (
            "CREATE INDEX idx_wb_outsourcing_members_receipt ON WorkbenchOutsourcingMembers(outsourcing_ref)"
        ),
        "idx_wb_outsourcing_receipts_batch": (
            "CREATE INDEX idx_wb_outsourcing_receipts_batch ON WorkbenchOutsourcingReceipts(batch_ref, outsourcing_ref)"
        ),
        "idx_wb_outsourcing_receipts_awaiting": (
            "CREATE INDEX idx_wb_outsourcing_receipts_awaiting "
            "ON WorkbenchOutsourcingReceipts(outsourcing_ref, planned) WHERE returned IS NULL"
        ),
        "idx_wb_outsourcing_receipts_returned": (
            "CREATE INDEX idx_wb_outsourcing_receipts_returned "
            "ON WorkbenchOutsourcingReceipts(outsourcing_ref) WHERE returned IS NOT NULL"
        ),
        "idx_wb_outsourcing_external_ops": (
            "CREATE INDEX idx_wb_outsourcing_external_ops "
            "ON BatchOperations(batch_id COLLATE NOCASE, piece_id COLLATE NOCASE, seq, id) WHERE source='external'"
        ),
        "WorkbenchOutsourcingFacts": """CREATE TABLE WorkbenchOutsourcingFacts (
            fact_ref """ + _REF.format("fact_ref") + """ PRIMARY KEY, outsourcing_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0), previous_fact_ref TEXT,
            sent TEXT NOT NULL, planned TEXT NOT NULL, returned TEXT,
            confirmed_state TEXT NOT NULL """ + _CONFIRMED_STATE + """,
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator))>0),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator))>0),
            reason TEXT NOT NULL CHECK(length(trim(reason))>0), recorded_at TEXT NOT NULL,
            before_json TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(outsourcing_ref,sequence), UNIQUE(previous_fact_ref),
            CHECK(planned>=sent AND (returned IS NULL OR returned>=sent)),
            CHECK(sent<=recorded_at AND (returned IS NULL OR returned<=recorded_at)),
            CHECK((confirmed_state='""" + OutsourcingConfirmedState.RETURNED.value + """')=(returned IS NOT NULL)),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref),
            FOREIGN KEY(previous_fact_ref) REFERENCES WorkbenchOutsourcingFacts(fact_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED)""",
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
        "wb_outsourcing_receipts_identity_immutable": """CREATE TRIGGER wb_outsourcing_receipts_identity_immutable
            BEFORE UPDATE ON WorkbenchOutsourcingReceipts
            WHEN NEW.outsourcing_ref IS NOT OLD.outsourcing_ref
              OR NEW.target_kind IS NOT OLD.target_kind
              OR NEW.batch_ref IS NOT OLD.batch_ref
              OR NEW.supplier_ref IS NOT OLD.supplier_ref
              OR NEW.origin_json IS NOT OLD.origin_json
              OR NEW.identity_json IS NOT OLD.identity_json
              OR NEW.created_at IS NOT OLD.created_at
              OR NEW.history_count IS NOT OLD.history_count + 1
            BEGIN SELECT RAISE(ABORT,'outsourcing receipt identity is immutable'); END""",
        "wb_outsourcing_receipts_no_delete": (
            "CREATE TRIGGER wb_outsourcing_receipts_no_delete BEFORE DELETE ON WorkbenchOutsourcingReceipts "
            "BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END"
        ),
        "wb_outsourcing_receipts_no_replace": (
            "CREATE TRIGGER wb_outsourcing_receipts_no_replace BEFORE INSERT ON WorkbenchOutsourcingReceipts "
            "WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=NEW.outsourcing_ref) "
            "BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END"
        ),
    }
    conflicts = {
        "Members": "operation_ref=NEW.operation_ref",
        "Facts": "fact_ref=NEW.fact_ref OR request_key=NEW.request_key OR (outsourcing_ref=NEW.outsourcing_ref AND sequence=NEW.sequence)",
    }
    for suffix, condition in conflicts.items():
        table = "WorkbenchOutsourcing" + suffix
        for event in ("UPDATE", "DELETE"):
            name = "wb_outsourcing_" + suffix.lower() + "_no_" + event.lower()
            objects[name] = (
                "CREATE TRIGGER " + name + " BEFORE " + event + " ON " + table +
                " BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END"
            )
        name = "wb_outsourcing_" + suffix.lower() + "_no_replace"
        objects[name] = (
            "CREATE TRIGGER " + name + " BEFORE INSERT ON " + table + " WHEN EXISTS(SELECT 1 FROM " +
            table + " WHERE " + condition + ") BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END"
        )
    return objects


def workbench_outsourcing_contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_outsourcing_schema:" if name not in actual else "invalid_outsourcing_schema:") + name
            for name, sql in workbench_outsourcing_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
