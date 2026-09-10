"""Bounded original template/instance reads. This repository cannot write lineage."""

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.models.workbench_calibration import MAX_OPERATIONS, MAX_TEMPLATES, CalibrationTemplate
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import MAX_FACT_ROWS, public_ref

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchCalibrationQueryRepository(BaseRepository):
    def require_schema(self):
        if workbench_metadata_contract_issues(self.conn) or workbench_process_contract_issues(self.conn):
            raise WorkbenchCommandRejected("calibration_source_unavailable", "模板永久身份或修订结构未就绪，本次读取没有补表或补身份。")

    def templates(self, query):
        if query.part_ref is not None and self.fetchone(
                "SELECT 1 FROM WorkbenchEntityRefs WHERE ref=? AND kind='part' AND active=1", (query.part_ref,)) is None:
            raise WorkbenchCommandRejected("entity_not_found", "零件永久引用已失效，不会改指同号零件。", 404)
        rows = self.fetchall("""SELECT o.*, r.ref AS operation_ref, r.revision, p.part_name,
            pr.ref AS part_ref FROM PartOperations o LEFT JOIN Parts p ON p.part_no=o.part_no
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
                AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=o.part_no
            WHERE o.status='active' AND (? IS NULL OR pr.ref=?)
            ORDER BY o.part_no,o.seq,o.id LIMIT ?""", (query.part_ref, query.part_ref, MAX_TEMPLATES + 1))
        if len(rows) > MAX_TEMPLATES:
            raise WorkbenchCommandRejected("query_too_large", "模板范围超过10000道，请按零件缩小范围；未截断数据。", 413)
        result = []
        for row in rows:
            if row["operation_ref"] is None or row["part_ref"] is None or type(row["revision"]) is not int or row["revision"] < 1:
                raise WorkbenchCommandRejected("calibration_source_unavailable", "模板或所属零件的永久身份缺失，不能补配。")
            public_ref(row["operation_ref"])
            public_ref(row["part_ref"])
            source = row["source"] if row["source"] in ("internal", "external") else "unknown"
            text = " ".join(str(row[key] or "") for key in ("part_no", "part_name", "op_type_name", "seq"))
            if query.source not in (None, source) or query.query.casefold() not in text.casefold():
                continue
            result.append(CalibrationTemplate(row["operation_ref"], row["revision"], row["part_ref"],
                row["part_no"], row["part_name"], row["seq"], row["op_type_name"], row["source"], row["unit_hours"]))
        return result

    def candidate_instances(self, part_numbers):
        """Same-part records are audit candidates only, NOT template sample matches."""
        result = []
        for chunk in chunks(sorted(set(part_numbers))):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT bo.op_code, bo.batch_id, bo.source, b.part_no,
                r.ref AS operation_ref FROM BatchOperations bo JOIN Batches b ON b.batch_id=bo.batch_id
                LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1
                    AND r.source_key=CAST(bo.id AS TEXT)
                WHERE b.part_no IN (""" + marks + ") ORDER BY b.part_no,bo.id LIMIT ?", chunk + [MAX_OPERATIONS + 1 - len(result)])
            result.extend(rows)
            if len(result) > MAX_OPERATIONS:
                raise WorkbenchCommandRejected("query_too_large", "待核对执行工序超过10000道，请缩小零件范围；未截断样本。", 413)
        if any(row["operation_ref"] is None for row in result):
            raise WorkbenchCommandRejected("calibration_source_unavailable", "执行实例永久身份缺失，不能按批次号或工序号补配。")
        return result

    def report_heads(self, operation_refs):
        result = set()
        for chunk in chunks(operation_refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT report_ref FROM WorkbenchProductionReports WHERE operation_ref IN (" + marks +
                                 ") LIMIT ?", chunk + [MAX_FACT_ROWS + 1 - len(result)])
            result.update(row["report_ref"] for row in rows)
            if len(result) > MAX_FACT_ROWS:
                raise WorkbenchCommandRejected("query_too_large", "报工来源超过50000条，未截断历史。", 413)
        return result
