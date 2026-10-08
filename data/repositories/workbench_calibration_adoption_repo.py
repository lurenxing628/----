"""Append-only adoption facts on the caller connection; rulings live in services."""

import secrets

from core.infrastructure.workbench_calibration_adoption_schema import contract_issues
from core.models.workbench_template_lineage import snapshot

from .base_repo import BaseRepository


class WorkbenchCalibrationAdoptionRepository(BaseRepository):
    def schema_installed(self):
        return not contract_issues(self.conn)

    def template(self, template_operation_ref):
        """Active template row joined with its permanent refs, or None; part_ref may be None."""
        return self.fetchone("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM WorkbenchEntityRefs r JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE r.ref=? AND r.kind='template_operation' AND r.active=1 AND o.status='active'""", (template_operation_ref,))

    def latest_adoption(self, template_operation_ref):
        return self.fetchone("""SELECT adoption_ref, template_operation_ref, old_unit_hours, new_unit_hours,
            template_revision_before, template_revision_after, reason, declared_operator, adopted_at
            FROM WorkbenchCalibrationAdoptions WHERE template_operation_ref=? ORDER BY rowid DESC LIMIT 1""",
            (template_operation_ref,))

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
               "evidence_json": evidence.audit_document(),
               "template_before": snapshot(before), "template_after": snapshot(after)}
        self.conn.execute("INSERT INTO WorkbenchCalibrationAdoptions (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        return {key: value for key, value in row.items() if key not in ("evidence_json", "template_before", "template_after")}
