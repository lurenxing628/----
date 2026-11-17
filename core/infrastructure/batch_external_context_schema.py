"""Frozen external scheduling context belongs to the batch operation, not its template."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import (
    BATCH_EXTERNAL_CONTEXT_ORIGIN_VALUES,
    MERGE_MODE_VALUES,
    SourceType,
    enum_check,
    nullable_enum_check,
    nullable_external_days_check,
)

from .schema_structure import SchemaStructure

_EXTERNAL = SourceType.EXTERNAL.value

_COLUMNS = (
    "operation_id", "part_no", "sequence", "template_operation_id", "template_status",
    "group_id", "group_part_no", "start_sequence", "end_sequence", "merge_mode",
    "total_days", "supplier_id", "group_ref", "template_operation_ref", "origin", "captured_at",
)


def capture_select(operation_sql, origin):
    """Fixed SQL fragments supplied only by this module."""
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
        WHERE o.source='""" + _EXTERNAL + "'"


def objects():
    capture = "INSERT INTO BatchExternalContexts(" + ",".join(_COLUMNS) + ") " + capture_select(
        "(SELECT * FROM BatchOperations WHERE id=NEW.id)", "creation") + ";"
    return {
        "BatchExternalContexts": f"""CREATE TABLE BatchExternalContexts (
            operation_id INTEGER PRIMARY KEY,
            part_no TEXT NOT NULL, sequence INTEGER NOT NULL,
            template_operation_id INTEGER, template_status TEXT,
            group_id TEXT, group_part_no TEXT, start_sequence INTEGER, end_sequence INTEGER,
            merge_mode TEXT {nullable_enum_check('merge_mode', MERGE_MODE_VALUES)},
            total_days REAL {nullable_external_days_check('total_days')}, supplier_id TEXT, group_ref TEXT,
            template_operation_ref TEXT,
            origin TEXT NOT NULL {enum_check('origin', BATCH_EXTERNAL_CONTEXT_ORIGIN_VALUES)},
            captured_at TEXT NOT NULL,
            FOREIGN KEY(operation_id) REFERENCES BatchOperations(id) ON DELETE CASCADE)""",
        "batch_external_context_created": """CREATE TRIGGER batch_external_context_created
            AFTER INSERT ON BatchOperations WHEN NEW.source='""" + _EXTERNAL + "' BEGIN " + capture + " END",
        "batch_external_context_source_changed": """CREATE TRIGGER batch_external_context_source_changed
            AFTER UPDATE OF source ON BatchOperations WHEN NEW.source='""" + _EXTERNAL + """'
                AND OLD.source IS NOT NEW.source
            BEGIN DELETE FROM BatchExternalContexts WHERE operation_id=NEW.id; """ + capture + " END",
    }


def contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_batch_external_context:" if name not in actual else "invalid_batch_external_context:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name])]
