"""Bounded original template/instance reads. This repository cannot write lineage or rule on it."""

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchCalibrationQueryRepository(BaseRepository):
    def schema_installed(self):
        memo = schema_contract_memo(self.conn)
        return not (memo.get_schema(workbench_metadata_contract_issues) or
                    memo.get_schema(workbench_process_contract_issues))

    def part_identity(self, part_ref):
        """Active part identity's stored entity key, or None when the ref is no longer live."""
        return self.fetchone("SELECT entity_key FROM WorkbenchEntityRefs WHERE ref=? AND kind='part' AND active=1", (part_ref,))

    def template_rows(self, part_no, limit):
        """Active templates with their permanent refs (may be NULL); reads at most limit+1 rows."""
        where, params = (" AND o.part_no=?", (part_no,)) if part_no is not None else ("", ())
        return self.fetchall("""SELECT o.*, r.ref AS operation_ref, r.revision, p.part_name,
            pr.ref AS part_ref FROM PartOperations o LEFT JOIN Parts p ON p.part_no=o.part_no
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
                AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=o.part_no
            WHERE o.status='active'""" + where + " ORDER BY o.part_no,o.seq,o.id LIMIT ?", params + (limit + 1,))

    def candidate_instance_rows(self, part_numbers, limit):
        """Same-part records are audit candidates only, NOT template sample matches.

        Reads at most limit+1 rows in total and stops as soon as the limit is exceeded.
        """
        result = []
        for chunk in chunks(sorted(set(part_numbers))):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT bo.*, b.part_no, b.quantity, b.quantity AS batch_quantity,
                r.ref AS operation_ref, r.active AS identity_active,
                br.ref AS batch_ref, pr.ref AS part_ref
                FROM BatchOperations bo JOIN Batches b ON b.batch_id=bo.batch_id
                LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1
                    AND r.source_key=CAST(bo.id AS TEXT)
                LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
                LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
                WHERE b.part_no IN (""" + marks + ") ORDER BY b.part_no,bo.id LIMIT ?", chunk + [limit + 1 - len(result)])
            result.extend(rows)
            if len(result) > limit:
                break
        return result
