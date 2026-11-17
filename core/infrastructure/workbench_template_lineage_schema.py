"""Immutable template lineage origins and O(1) one-way instance modification flags."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import flag_check

from .schema_structure import SchemaStructure

_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"
_MODIFIED_OPERATION_COLUMNS = (
    "piece_id", "seq", "op_type_id", "op_type_name", "source",
    "supplier_id", "setup_hours", "unit_hours", "ext_days", "batch_id",
)


def _source_triggers():
    current_ref = (
        "(SELECT ref FROM WorkbenchPlanSourceRefs"
        " WHERE kind='operation' AND active=1 AND source_key=CAST(OLD.id AS TEXT))"
    )
    changed = " OR ".join(f"OLD.{key} IS NOT NEW.{key}" for key in _MODIFIED_OPERATION_COLUMNS)
    return {
        "wb_lineage_operation_update": (
            f"CREATE TRIGGER wb_lineage_operation_update BEFORE UPDATE ON BatchOperations "
            f"WHEN {changed} BEGIN "
            f"UPDATE WorkbenchTemplateLineageOrigins SET instance_modified=1 "
            f"WHERE operation_ref={current_ref} AND instance_modified=0; END"
        ),
        "wb_lineage_batch_change": (
            "CREATE TRIGGER wb_lineage_batch_change AFTER UPDATE ON Batches "
            "WHEN OLD.part_no IS NOT NEW.part_no OR OLD.quantity IS NOT NEW.quantity BEGIN "
            "UPDATE WorkbenchTemplateLineageOrigins SET instance_modified=1 "
            "WHERE instance_modified=0 AND operation_ref IN ("
            "SELECT r.ref FROM BatchOperations o JOIN WorkbenchPlanSourceRefs r "
            "ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT) "
            "WHERE o.batch_id=NEW.batch_id); END"
        ),
    }


def template_lineage_objects():
    objects = {
        "WorkbenchTemplateLineageOrigins": """CREATE TABLE WorkbenchTemplateLineageOrigins (
            lineage_ref """ + _REF.format("lineage_ref") + """ PRIMARY KEY,
            operation_ref TEXT NOT NULL UNIQUE,
            template_operation_ref TEXT NOT NULL,
            template_revision INTEGER NOT NULL CHECK(typeof(template_revision)='integer' AND template_revision>0),
            source_eligible INTEGER NOT NULL """ + flag_check("source_eligible") + """,
            instance_modified INTEGER NOT NULL DEFAULT 0 """ + flag_check("instance_modified") + """,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(template_operation_ref) REFERENCES WorkbenchEntityRefs(ref)
        )""",
        "idx_wb_lineage_template_revision": (
            "CREATE INDEX idx_wb_lineage_template_revision "
            "ON WorkbenchTemplateLineageOrigins(template_operation_ref,template_revision)"
        ),
    }
    objects.update(_source_triggers())
    objects["wb_lineage_origin_no_update"] = (
        "CREATE TRIGGER wb_lineage_origin_no_update BEFORE UPDATE ON WorkbenchTemplateLineageOrigins "
        "WHEN NEW.lineage_ref IS NOT OLD.lineage_ref "
        "OR NEW.operation_ref IS NOT OLD.operation_ref "
        "OR NEW.template_operation_ref IS NOT OLD.template_operation_ref "
        "OR NEW.template_revision IS NOT OLD.template_revision "
        "OR NEW.source_eligible IS NOT OLD.source_eligible "
        "OR OLD.instance_modified != 0 OR NEW.instance_modified != 1 "
        "BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END"
    )
    objects["wb_lineage_origin_no_delete"] = (
        "CREATE TRIGGER wb_lineage_origin_no_delete BEFORE DELETE ON WorkbenchTemplateLineageOrigins "
        "BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END"
    )
    objects["wb_lineage_origin_birth"] = """CREATE TRIGGER wb_lineage_origin_birth BEFORE INSERT ON WorkbenchTemplateLineageOrigins BEGIN
        SELECT CASE WHEN NEW.instance_modified != 0 OR NOT EXISTS (
            SELECT 1 FROM WorkbenchPlanSourceRefs r
            WHERE r.ref=NEW.operation_ref AND r.kind='operation' AND r.active=1
        ) THEN RAISE(ABORT,'template lineage requires a new instance birth') END;
        SELECT CASE WHEN EXISTS (
            SELECT 1 FROM WorkbenchTemplateLineageOrigins
            WHERE operation_ref=NEW.operation_ref OR lineage_ref=NEW.lineage_ref
        ) THEN RAISE(ABORT,'template lineage cannot be rebound') END;
    END"""
    return objects


def template_lineage_contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_template_lineage:" if name not in actual else "invalid_template_lineage:") + name
            for name, sql in template_lineage_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
