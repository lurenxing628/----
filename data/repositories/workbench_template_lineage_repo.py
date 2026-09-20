"""Exact identity lookups and append-only copy evidence in the caller transaction; no rulings here."""

import secrets

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_template_lineage_schema import contract_issues, objects
from core.models.workbench_template_lineage import (
    COPY_COLUMNS,
    EVIDENCE_VERSION,
    STATE_COLUMNS,
    fingerprint,
    state_snapshot,
)

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


def _size_expression(columns):
    return "+".join('COALESCE(length(CAST("' + column + '" AS BLOB)),0)' for column in columns)


# Fixed evidence tables only; the size SQL is expanded here instead of from caller-supplied names.
EVIDENCE_SIZE_SQL = {
    "origins": ("SELECT COALESCE(sum(" + _size_expression(("template_snapshot", "instance_snapshot")) +
                "),0) AS bytes FROM WorkbenchTemplateLineageOrigins WHERE operation_ref IN ("),
    "events": ("SELECT COALESCE(sum(" + _size_expression(STATE_COLUMNS + ("operation_ref", "reason", "recorded_at_utc")) +
               "),0) AS bytes FROM WorkbenchTemplateLineageEvents WHERE operation_ref IN ("),
}
EXECUTION_FACT_PROBES = (
    ("WorkbenchProductionReports", "SELECT 1 FROM WorkbenchProductionReports WHERE operation_ref=? LIMIT 1"),
    ("WorkbenchExecutionLegacyFacts", "SELECT 1 FROM WorkbenchExecutionLegacyFacts WHERE operation_ref=? LIMIT 1"),
)


class WorkbenchTemplateLineageRepository(BaseRepository):
    def schema_state(self):
        """'missing' (no lineage objects), 'invalid' (partial/altered DDL) or 'loaded'."""
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master")}
        if not names & set(objects()):
            return "missing"
        return "invalid" if contract_issues(self.conn) else "loaded"

    def identity_schema_broken(self):
        return bool(workbench_metadata_contract_issues(self.conn) or workbench_process_contract_issues(self.conn) or
                    workbench_plan_identity_contract_issues(self.conn))

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
                p.ref AS part_ref FROM WorkbenchEntityRefs r LEFT JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
                LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
                WHERE r.kind='template_operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["template_operation_ref"], row) for row in rows)
        return result

    def instance(self, operation_id):
        """Batch operation row with operation/batch/part refs (may be NULL), or None."""
        return self.fetchone("""SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
            FROM BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
            LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
            WHERE o.id=?""", (operation_id,))

    def current_instances(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
                FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o ON r.source_key=CAST(o.id AS TEXT)
                JOIN Batches b ON b.batch_id=o.batch_id
                LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
                LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
                WHERE r.kind='operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["operation_ref"], row) for row in rows)
        return result

    def insert_instance(self, payload):
        cursor = self.execute("INSERT INTO BatchOperations (" + ",".join(COPY_COLUMNS) + ") VALUES (" +
                              ",".join("?" for _ in COPY_COLUMNS) + ")", tuple(payload[key] for key in COPY_COLUMNS))
        return self.instance(cursor.lastrowid)

    def origins_bytes(self, refs):
        return self._evidence_bytes("origins", refs)

    def origins(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT * FROM WorkbenchTemplateLineageOrigins WHERE operation_ref IN (" + marks + ")", chunk):
                result[row["operation_ref"]] = row
        return result

    def events_bytes(self, refs):
        return self._evidence_bytes("events", refs)

    def event_chunks(self, refs, limit):
        """Ordered event rows per ref chunk; each chunk reads at most limit+1 rows and reading stops once exceeded."""
        result = []
        total = 0
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT * FROM WorkbenchTemplateLineageEvents WHERE operation_ref IN (" + marks +
                                 ") ORDER BY event_id LIMIT ?", chunk + [limit + 1])
            result.append(rows)
            total += len(rows)
            if len(rows) > limit or total > limit:
                break
        return result

    def _evidence_bytes(self, kind, refs):
        size = 0
        for chunk in chunks(refs):
            row = self.fetchone(EVIDENCE_SIZE_SQL[kind] + ",".join("?" for _ in chunk) + ")", chunk)
            if row is None:
                raise RuntimeError("Cannot read lineage evidence size.")
            size += row["bytes"]
        return size

    def has_execution_facts(self, operation_ref):
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return any(table in names and self.fetchone(sql, (operation_ref,)) for table, sql in EXECUTION_FACT_PROBES)

    def has_legacy_execution_events(self, operation_id):
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return "OperationExecutionEvents" in names and self.fetchone(
            "SELECT 1 FROM OperationExecutionEvents WHERE op_id=? LIMIT 1", (operation_id,)) is not None

    def append_origin(self, instance, template, template_snapshot, *, birth_event_id, source=None, source_event_id=None,
                      source_eligible=True):
        encoded = state_snapshot(instance)
        row = dict(lineage_ref=secrets.token_hex(24), operation_ref=instance["operation_ref"],
                   template_operation_ref=template["template_operation_ref"], template_revision=template["template_revision"],
                   source_operation_ref=source["operation_ref"] if source else None,
                   source_lineage_ref=source["lineage_ref"] if source else None, source_event_id=source_event_id,
                   source_eligible=int(source_eligible), birth_event_id=birth_event_id,
                   evidence_version=EVIDENCE_VERSION, template_snapshot=template_snapshot,
                   template_fingerprint=fingerprint(template_snapshot), instance_snapshot=encoded, instance_fingerprint=fingerprint(encoded))
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageOrigins (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        return row

    def append_withdrawn_event(self, operation_ref, reason, last_event):
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,reason," +
                          ",".join(STATE_COLUMNS) + ") VALUES (?,'withdrawn',1,?," + ",".join("?" for _ in STATE_COLUMNS) + ")",
                          (operation_ref, reason) + tuple(last_event[key] for key in STATE_COLUMNS))
