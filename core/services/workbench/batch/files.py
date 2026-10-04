"""Preview-first batch file service, reusing existing batch validators and CRUD."""

import hashlib

from core.errors import ValidationError
from core.models.workbench_batch_file import COLUMNS
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected

from .facts import BatchFacts, index_relations
from .file_codec import read_batch_file, write_batch_file
from .file_preview import BatchImportPreview, file_values
from .service import WorkbenchBatchService


class WorkbenchBatchFileService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.reader = reader if reader is not None else BatchFacts(conn, logger)
        self.domain = WorkbenchBatchService(conn, logger, facts=self.reader)

    @staticmethod
    def read(content, mode):
        """Check the mode and parse the workbook; needs no ledger, so routes do it before a read snapshot."""
        if mode not in ("overwrite", "append", "replace"):
            raise WorkbenchCommandRejected("invalid_input", "批次导入方式选得不对。", 400)
        parsed, warnings = read_batch_file(content)
        if not parsed:
            raise ValidationError("文件里一行批次数据都没有，不能用空文件清除已有资料。", field="file")
        return parsed, warnings

    def preview(self, content, mode, upload=None):
        parsed, warnings = upload if upload is not None else self.read(content, mode)
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
        # 第一次写入前算好全部批次的关联：替换模式一次删完，改数量的行也不再每行重读整本批次数据。
        index = index_relations(self.reader.load()) if any(row["action"] == "update" for row in document["rows"]) else None
        self.domain.delete_many([row["entity_ref"] for row in document["deleted"]])
        outcomes = []
        for row in document["rows"]:
            if row["action"] in ("skipped", "unchanged"):
                outcomes.append({"entity_ref": row["entity_ref"], "business_code": row["business_code"], "result": row["action"]})
                continue
            result = self.domain.apply(row["action"], row["input"], row["entity_ref"] if row["action"] == "update" else None,
                                       relations_index=index)
            outcomes.append({**result.data, "result": result.result})
        changed = bool(document["deleted"]) or any(row["result"] == "committed" for row in outcomes)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"items": outcomes, "count": len(outcomes),
            "deleted_count": len(document["deleted"]), "deleted_refs": [row["entity_ref"] for row in document["deleted"]],
            "mode": document["mode"], "file_sha256": document["file_sha256"], "commit_policy": "atomic"}, document["warnings"])

    @staticmethod
    def export(entities):
        from core.services.common.enum_normalizers import ready_status_label

        rows = []
        for entity in entities:
            # 与回导比对共用同一份写法，原样导回才能逐格判断“没动”。
            data = file_values(entity)
            status = {"pending": "待排", "scheduled": "已排", "processing": "加工中", "completed": "已完成", "cancelled": "已取消"}.get(entity["status"], entity["status"])
            effective_ready = entity["display_ready_status"]
            if effective_ready in ("yes", "partial", "no"):
                effective_ready = ready_status_label(effective_ready)
            rows.append([data[key] for key in COLUMNS] + [status, effective_ready])
        return write_batch_file(rows)
