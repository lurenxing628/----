"""Quota-lock facts and atomic audit writes on the caller connection; rulings live in services."""

import secrets

from core.infrastructure.workbench_calibration_adoption_schema import contract_issues
from core.models.workbench_command import canonical_json
from core.models.workbench_template_lineage import snapshot

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchCalibrationAdoptionRepository(BaseRepository):
    def schema_installed(self):
        return not contract_issues(self.conn)

    def template(self, template_operation_ref):
        """Active template row joined with its permanent refs, or None; part_ref may be None."""
        return self.fetchone("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM WorkbenchEntityRefs r JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE r.ref=? AND r.kind='template_operation' AND r.active=1 AND o.status='active'""", (template_operation_ref,))

    def lock_pairs(self, template_operation_refs):
        """Per chunk: (template refs holding an adoption audit, lock rows joined with their audit).

        This method never starts/commits a transaction, installs storage, or resolves codes;
        the service compares both sides and decides whether the pair is corrupt.
        """
        result = []
        for chunk in chunks(list(template_operation_refs)):
            marks = ",".join("?" for _ in chunk)
            audits = self.fetchall("SELECT template_operation_ref,adoption_ref FROM WorkbenchCalibrationAdoptions "
                                   "WHERE template_operation_ref IN (" + marks + ")", chunk)
            rows = self.fetchall("""SELECT l.*, a.template_operation_ref AS audit_template_ref,
                a.new_unit_hours, a.adopted_at, a.reason, a.declared_operator, a.confirmed, a.application_operator, a.method_version,
                a.sample_count, a.template_revision_after, a.request_key
                FROM WorkbenchCalibrationQuotaLocks l LEFT JOIN WorkbenchCalibrationAdoptions a
                ON a.adoption_ref=l.adoption_ref WHERE l.template_operation_ref IN (""" + marks + ")", chunk)
            result.append(({row["template_operation_ref"] for row in audits}, rows))
        return result

    def update_quota(self, template, value):
        """Guarded UPDATE of one template quota; returns the affected row count."""
        if not self.conn.in_transaction:
            raise RuntimeError("Quota adoption requires the caller write transaction.")
        cursor = self.conn.execute("""UPDATE PartOperations SET unit_hours=? WHERE id=? AND unit_hours IS ?
            AND EXISTS (SELECT 1 FROM WorkbenchEntityRefs WHERE kind='template_operation' AND active=1
            AND ref=? AND revision=? AND entity_key=CAST(PartOperations.id AS TEXT))""",
            (value, template["id"], template["unit_hours"], template["template_operation_ref"], template["template_revision"]))
        return cursor.rowcount

    def append(self, evidence, after, intent, *, request_key, actor, adopted_at):
        if not self.conn.in_transaction:
            raise RuntimeError("Calibration audit requires the caller write transaction.")
        before, suggestion = evidence.template, evidence.suggestion
        row = {"adoption_ref": secrets.token_hex(24), "template_operation_ref": before["template_operation_ref"],
               "request_key": request_key, "template_revision_before": before["template_revision"],
               "template_revision_after": after["template_revision"], "old_unit_hours": before["unit_hours"],
               "new_unit_hours": after["unit_hours"], "reason": intent["reason"],
               "declared_operator": intent["declared_operator"], "confirmed": intent["confirm"], "application_operator": actor,
               "adopted_at": adopted_at, "generated_at": evidence.generated_at,
               "method_version": suggestion["method_version"], "sample_count": suggestion["sample_count"],
               "evidence_json": canonical_json({"snapshot": evidence.snapshot, "suggestion": suggestion, "samples": evidence.samples}),
               "template_before": snapshot(before), "template_after": snapshot(after)}
        self.conn.execute("INSERT INTO WorkbenchCalibrationAdoptions (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        self.conn.execute("""INSERT INTO WorkbenchCalibrationQuotaLocks
            (template_operation_ref,adoption_ref,locked_unit_hours,locked_at) VALUES (?,?,?,?)""",
            (row["template_operation_ref"], row["adoption_ref"], row["new_unit_hours"], adopted_at))
        return {key: value for key, value in row.items() if key not in ("evidence_json", "template_before", "template_after")}
