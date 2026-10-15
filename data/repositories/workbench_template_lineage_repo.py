"""Exact identity lookups and append-only copy evidence in the caller transaction; no rulings here."""

import secrets

from core.infrastructure.connection_guards import SchemaContractMemo
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_template_lineage_schema import contract_issues, objects
from core.models.workbench_template_lineage import (
    COPY_COLUMNS,
    EVIDENCE_VERSION,
    STATE_COLUMNS,
)

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


def _size_expression(columns):
    return "+".join('COALESCE(length(CAST("' + column + '" AS BLOB)),0)' for column in columns)


# Fixed evidence tables only; the size SQL is expanded here instead of from caller-supplied names.
EVIDENCE_SIZE_SQL = {
    "origins": _size_expression(("template_snapshot", "instance_snapshot")),
    "events": _size_expression(STATE_COLUMNS + ("operation_ref", "reason", "recorded_at_utc")),
}

INSTANCE_SELECT = """SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity"""
INSTANCE_FROM = """ FROM BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id
    LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
    LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
    LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no"""


def _schema_state(conn, *, structure):
    if not structure.objects.keys() & objects().keys():
        return "missing"
    return "invalid" if contract_issues(conn, structure=structure) else "loaded"


def _identity_schema_broken(conn, *, structure):
    return bool(workbench_metadata_contract_issues(conn, structure=structure)
                or workbench_process_contract_issues(conn, structure=structure)
                or workbench_plan_identity_contract_issues(conn, structure=structure))


class WorkbenchTemplateLineageRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        # 同一命令逐道复制共用结构事实；命令内不执行 DDL，下一请求新建仓储。
        self.contracts = SchemaContractMemo(conn)

    def schema_state(self):
        """'missing' (no lineage objects), 'invalid' (partial/altered DDL) or 'loaded'."""
        return self.contracts.get_schema(_schema_state)

    def identity_schema_broken(self):
        return self.contracts.get_schema(_identity_schema_broken)

    def template(self, template_id):
        """Active template row with permanent refs (may be NULL), or None."""
        return self.fetchone("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE o.id=? AND o.status='active'""", (template_id,))

    def current_templates(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
                p.ref AS part_ref FROM WorkbenchEntityRefs r LEFT JOIN PartOperations o
                ON o.id=CAST(r.entity_key AS INTEGER) AND CAST(o.id AS TEXT)=r.entity_key
                LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
                WHERE r.kind='template_operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["template_operation_ref"], row) for row in rows)
        return result

    def templates_for_part(self, part_no):
        return self.fetchall("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE o.part_no=? AND o.status='active' ORDER BY o.seq""", (part_no,))

    def instance(self, operation_id):
        """Batch operation row with operation/batch/part refs (may be NULL), or None."""
        return self.fetchone(INSTANCE_SELECT + INSTANCE_FROM + " WHERE o.id=?", (operation_id,))

    def current_instances(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
                FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o
                ON o.id=CAST(r.source_key AS INTEGER) AND CAST(o.id AS TEXT)=r.source_key
                JOIN Batches b ON b.batch_id=o.batch_id
                LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
                LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
                WHERE r.kind='operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["operation_ref"], row) for row in rows)
        return result

    def insert_instance(self, payload):
        cursor = self.execute("INSERT INTO BatchOperations (" + ",".join(COPY_COLUMNS) + ") VALUES (" +
                              ",".join("?" for _ in COPY_COLUMNS) + ")", tuple(payload[key] for key in COPY_COLUMNS))
        return self.fetchone(INSTANCE_SELECT + ", e.event_id AS birth_event_id" + INSTANCE_FROM +
            " LEFT JOIN WorkbenchTemplateLineageEvents e ON e.operation_ref=r.ref AND e.event_type='created' WHERE o.id=?",
            (cursor.lastrowid,))

    def origin_rows(self, refs):
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            yield from self.iter_rows("SELECT *, " + EVIDENCE_SIZE_SQL["origins"] +
                " AS _lineage_bytes FROM WorkbenchTemplateLineageOrigins WHERE operation_ref IN (" + marks + ")", chunk)

    def origins(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT * FROM WorkbenchTemplateLineageOrigins WHERE operation_ref IN (" + marks + ")", chunk):
                result[row["operation_ref"]] = row
        return result

    def event_chunks(self, refs, limit):
        """Stream body rows, with one global budget across all ref chunks."""
        total = 0

        def counted(rows):
            nonlocal total
            for row in rows:
                total += 1
                yield row

        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.iter_rows("SELECT *, " + EVIDENCE_SIZE_SQL["events"] +
                " AS _lineage_bytes FROM WorkbenchTemplateLineageEvents WHERE operation_ref IN (" + marks +
                ") ORDER BY event_id LIMIT ?", chunk + [limit - total + 1])
            yield counted(rows)
            if total > limit:
                break

    def append_origin(self, instance, template, template_snapshot, instance_snapshot, *, birth_event_id, source=None, source_event_id=None,
                      source_eligible=True):
        row = dict(lineage_ref=secrets.token_hex(24), operation_ref=instance["operation_ref"],
                   template_operation_ref=template["template_operation_ref"], template_revision=template["template_revision"],
                   source_operation_ref=source["operation_ref"] if source else None,
                   source_lineage_ref=source["lineage_ref"] if source else None, source_event_id=source_event_id,
                   source_eligible=int(source_eligible), birth_event_id=birth_event_id,
                   evidence_version=EVIDENCE_VERSION, template_snapshot=template_snapshot,
                   template_fingerprint=None, instance_snapshot=instance_snapshot, instance_fingerprint=None)
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageOrigins (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        return row

    def append_withdrawn_event(self, operation_ref, reason, last_event):
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,reason," +
                          ",".join(STATE_COLUMNS) + ") VALUES (?,'withdrawn',1,?," + ",".join("?" for _ in STATE_COLUMNS) + ")",
                          (operation_ref, reason) + tuple(last_event[key] for key in STATE_COLUMNS))
