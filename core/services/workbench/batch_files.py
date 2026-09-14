"""Preview-first batch file service, reusing existing batch validators and CRUD."""

import hashlib

from core.errors import ValidationError
from core.models.workbench_batch_file import COLUMNS
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.workbench.batch_facts import BatchFacts
from core.services.workbench.batch_file_codec import read_batch_file, write_batch_file
from core.services.workbench.batch_file_preview import BatchImportPreview
from core.services.workbench.batches import WorkbenchBatchService


class WorkbenchBatchFileService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.reader = BatchFacts(conn, logger)
        self.domain = WorkbenchBatchService(conn, logger)

    def preview(self, content, mode):
        if mode not in ("overwrite", "append", "replace"):
            raise WorkbenchCommandRejected("invalid_input", "批次导入方式选得不对。", 400)
        parsed, warnings = read_batch_file(content)
        if not parsed:
            raise ValidationError("文件里一行批次数据都没有，不能用空文件清除已有资料。", field="file")
        preview = BatchImportPreview(self.reader.load(), mode)
        rows = [preview.row(row) for row in parsed]
        deleted = preview.deleted()
        can_confirm = not any(row["errors"] for row in rows + deleted)
        return {"operation": "batch.import_confirm", "mode": mode, "file_sha256": hashlib.sha256(content).hexdigest(),
                "rows": rows, "deleted": deleted, "count": len(rows), "commit_policy": "atomic", "can_confirm": can_confirm,
                "auto_generate_operations": False, "warnings": warnings}

    def apply(self, document):
        if not self.conn.in_transaction:
            raise RuntimeError("批次文件确认必须由工作台命令事务持有。")
        if document["operation"] != "batch.import_confirm" or not document["can_confirm"]:
            raise WorkbenchCommandRejected("constraint_conflict", "预检里还有不能通过的行，系统一条批次都没有写入。")
        for row in document["deleted"]:
            self.domain.apply("delete", {}, row["entity_ref"])
        outcomes = []
        for row in document["rows"]:
            if row["action"] == "skipped":
                outcomes.append({"entity_ref": row["entity_ref"], "business_code": row["business_code"], "result": "skipped"})
                continue
            result = self.domain.apply(row["action"], row["input"], row["entity_ref"] if row["action"] == "update" else None)
            outcomes.append({**result.data, "result": result.result})
        changed = bool(document["deleted"]) or any(row["result"] == "committed" for row in outcomes)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"items": outcomes, "count": len(outcomes),
            "deleted_count": len(document["deleted"]), "deleted_refs": [row["entity_ref"] for row in document["deleted"]],
            "mode": document["mode"], "file_sha256": document["file_sha256"], "commit_policy": "atomic"}, document["warnings"])

    @staticmethod
    def export(entities):
        from core.services.common.enum_normalizers import batch_priority_label, ready_status_label

        rows = []
        for entity in entities:
            data = {"business_code": entity["business_code"], "part_no": entity["relationships"]["part_no"], **entity["fields"]}
            if data["priority"] in ("normal", "urgent", "critical"):
                data["priority"] = batch_priority_label(data["priority"])
            if data["ready_status"] in ("yes", "partial", "no"):
                data["ready_status"] = ready_status_label(data["ready_status"])
            status = {"pending": "待排", "scheduled": "已排", "processing": "加工中", "completed": "已完成", "cancelled": "已取消"}.get(entity["status"], entity["status"])
            rows.append([data[key] for key in COLUMNS] + [status])
        return write_batch_file(rows)
