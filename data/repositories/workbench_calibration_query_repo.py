"""Bounded original template/instance reads. This repository cannot write lineage or rule on it."""

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchCalibrationQueryRepository(BaseRepository):
    def schema_installed(self):
        return not (workbench_metadata_contract_issues(self.conn) or workbench_process_contract_issues(self.conn))

    def part_exists(self, part_ref):
        return self.fetchone("SELECT 1 FROM WorkbenchEntityRefs WHERE ref=? AND kind='part' AND active=1", (part_ref,)) is not None

    def template_rows(self, part_ref, limit):
        """Active templates with their permanent refs (may be NULL); reads at most limit+1 rows."""
        return self.fetchall("""SELECT o.*, r.ref AS operation_ref, r.revision, p.part_name,
            pr.ref AS part_ref FROM PartOperations o LEFT JOIN Parts p ON p.part_no=o.part_no
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
                AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=o.part_no
            WHERE o.status='active' AND (? IS NULL OR pr.ref=?)
            ORDER BY o.part_no,o.seq,o.id LIMIT ?""", (part_ref, part_ref, limit + 1))

    def candidate_instance_rows(self, part_numbers, limit):
        """Same-part records are audit candidates only, NOT template sample matches.

        Reads at most limit+1 rows in total and stops as soon as the limit is exceeded.
        """
        result = []
        for chunk in chunks(sorted(set(part_numbers))):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT bo.op_code, bo.batch_id, bo.source, b.part_no,
                r.ref AS operation_ref FROM BatchOperations bo JOIN Batches b ON b.batch_id=bo.batch_id
                LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1
                    AND r.source_key=CAST(bo.id AS TEXT)
                WHERE b.part_no IN (""" + marks + ") ORDER BY b.part_no,bo.id LIMIT ?", chunk + [limit + 1 - len(result)])
            result.extend(rows)
            if len(result) > limit:
                break
        return result

    def report_head_refs(self, operation_refs, limit):
        """Distinct report refs for the operations; reads at most limit+1 and stops when exceeded."""
        result = set()
        for chunk in chunks(list(operation_refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT report_ref FROM WorkbenchProductionReports WHERE operation_ref IN (" + marks +
                                 ") LIMIT ?", chunk + [limit + 1 - len(result)])
            result.update(row["report_ref"] for row in rows)
            if len(result) > limit:
                break
        return result
