"""Private material upsert/import/export orchestration; no Flask or token storage.

preview_import(content: bytes, *, file_format, mode) returns a
MaterialPreview. The upload route admits csv|xlsx and mode=upsert. Blank
cells/columns are omitted, \\N clears only nullable fields. Headers and
escaping are documented in material_file_codec.
created_at is exported for reference and is never part of imported changes.

confirm_import(preview) requires an outer CommandService write transaction. The
preview carries its parsed source (preview.source). Bind the original in-memory
preview to the API's temporary write context and pass {"preview_ref": ref} as
normalized_input. All facts/inputs are rechecked before writes; the outer command
transaction rolls back the whole batch on any domain failure. Referenced updates
are flagged requires_confirmation in the approved preview.

export_rows(file_format, *, request=None, selected_refs=None) requires the caller's
already validated read-snapshot transaction and exactly one validated
MaterialPageRequest or ref list. Pass that snapshot's reader to the service to
reuse its captured rows.
Filters export every matching row in query order; selected refs retain their
explicit order. The 2000-row import cap does not apply to either selection.
XLSX is limited only by worksheet capacity; CSV has no worksheet row/cell cap.
write_material_file(rows, file_format) encodes those rows after the read transaction
ends and returns FileDownload(filename, mime_type, content: bytes, row_count).
"""

from __future__ import annotations

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material import normalize_material_input
from core.models.workbench_material_file import (
    COLUMNS,
    MATERIAL_COLUMNS,
    MaterialPreview,
    preview_row,
    reject_row,
)
from core.models.workbench_resource_file_source import PreparedImportSource
from core.models.workbench_resource_input import resource_text
from core.services.workbench import messages
from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository

from .bulk import full_material_snapshot
from .file_codec import check_export_capacity, read_material_file
from .queries import WorkbenchMaterialQueryService
from .service import WorkbenchMaterialService
from .table_facts import MaterialRow


class WorkbenchMaterialFileService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.adapter = WorkbenchMaterialService(conn, logger=logger)
        self.reader = reader if reader is not None else WorkbenchMaterialQueryService(conn, logger=logger)
        self.repo = WorkbenchMaterialFileRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def _prepare_source(self, content, *, file_format, mode):
        request = {"format": file_format, "mode": mode}
        source, notices = read_material_file(content, file_format)
        return PreparedImportSource.build(request, source, notices)

    def preview_import(self, content, *, file_format, mode):
        prepared = self._prepare_source(content, file_format=file_format, mode=mode)
        with self.tx.transaction():
            preview, _ = self._prepare_import(prepared)
            return preview

    def _prepare_import(self, prepared):
        request = prepared.request()
        source, notices = prepared.parsed()
        rows = [self._coded_row(item) for item in source]
        captured = self.repo.capture(codes={row["business_code"] for row in rows if row["business_code"] is not None})
        for row, item in zip(rows, source):
            if row["business_code"] is not None:
                self._import_row(row, item["values"], captured)
        duplicates = {}
        for row in rows:
            if row["business_code"] is not None:
                duplicates.setdefault(row["business_code"], []).append(row)
        for repeated in duplicates.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(row["row"]) for row in repeated)
                for row in repeated:
                    reject_row(row, "同一编号在文件中重复，涉及行：" + numbers, code="duplicate_entry")
        return MaterialPreview.build("material.import", request, rows, notices, source=prepared), rows

    @staticmethod
    def _coded_row(source):
        """逐行用 resource_text 校验编号非空与非法字符并保留原值；预取和后续逐行比对都用这一份结果。"""
        row = preview_row(source["row"])
        row["errors"] = list(source["errors"])
        row["reference_fields"] = ["created_at"] if "created_at" in source["values"] else []
        try:
            resource_text(source["values"].get("business_code"), "business_code")
            row["business_code"] = source["values"]["business_code"]
        except ValidationError as exc:
            reject_row(row, exc.message)
        return row

    def _import_row(self, row, values, captured):
        code = row["business_code"]
        try:
            raw = captured["materials"].get(code)
            if raw is None and code != code.strip():
                raise ValidationError("物料编号不能有首尾空格，请修正后重新导入。", field="business_code")
            row["action"] = "create" if raw is None else "update"
            if raw is None:
                row["expected"] = {"identity": None, "material": None, "requirements": [],
                                   "identity_history": captured["identity_history"].get(code, [])}
            else:
                identity = captured["identities"].get(raw["ref"])
                identity = WorkbenchEntityIdentity(identity["ref"], identity["kind"], identity["entity_key"],
                                                    identity["revision"], bool(identity["active"])) if identity else None
                if identity is None:
                    raise WorkbenchCommandRejected("storage_failure", "这条物料缺少系统编号，请联系维护人员核对资料。", 500)
                row["expected"] = full_material_snapshot(captured, identity)
            if not row["errors"]:
                row["input"] = self._normalize_values(row["action"], code, values, raw)
                self._classify(row, raw)
        except ValidationError as exc:
            reject_row(row, exc.message, field=exc.field or "input")

    @staticmethod
    def _normalize_values(action, code, values, raw):
        if raw is None:
            payload = {
                "business_code": code,
                "fields": {key: value for key, value in values.items() if key not in ("business_code", "label", "created_at")},
            }
            if "label" in values:
                payload["label"] = values["label"]
            return normalize_material_input(action, payload)
        fields = {
            key: value
            for key, value in values.items()
            if key not in ("business_code", "label", "created_at")
            and (type(value) is bool or value != raw[key])
        }
        payload = {"fields": fields}
        if "label" in values and values["label"] != raw["name"]:
            payload["label"] = values["label"]
        return normalize_material_input(action, payload)

    @staticmethod
    def _classify(row, raw):
        if raw is None:
            row["result"] = "new"
            return
        normalized = row["input"]
        changes = {key: {"before": raw[key], "after": value} for key, value in normalized["fields"].items()
                   if raw[key] != value}
        if "label" in normalized and raw["name"] != normalized["label"]:
            changes["name"] = {"before": raw["name"], "after": normalized["label"]}
        row["changes"] = changes
        row["result"] = "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = bool(row["changes"] and row["expected"]["requirements"])

    def confirm_import(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("物料导入确认必须在外层工作台写事务中执行。")
        current, rows = self._prepare_import(preview.source)
        body = preview.check_current(current)
        changes = [self.adapter.prepare_checked(row["action"], row["input"], row["expected"]) for row in rows]
        outcomes = self.adapter.apply_prepared_many(changes)
        results = [{"row": row["row"], "result": outcome.result, **outcome.data}
                   for row, outcome in zip(rows, outcomes)]
        result = "committed" if any(row["result"] == "committed" for row in results) else "unchanged"
        return WorkbenchCommandOutcome(result, {"rows": results, "summary": body["summary"]})

    def export_rows(self, file_format, *, request=None, selected_refs=None):
        """在调用方已验证的读快照里读完整份导出行；编码文件交给 write_material_file，在读事务结束后做。"""
        snapshot = self.reader._snapshot
        if not self.conn.in_transaction or snapshot is None:
            raise RuntimeError("物料导出必须在调用方已验证的查询快照事务中执行。")
        if selected_refs is None:
            rows = self.reader.matching_rows(request)
            check_export_capacity(len(rows), file_format)
        else:
            check_export_capacity(len(selected_refs), file_format)
            rows = self.reader.selected_rows(selected_refs)
        return [self._export_row(row) for row in rows]

    @staticmethod
    def _export_row(row: MaterialRow):
        raw = row.raw
        exported = dict(zip(COLUMNS, (raw[key] for key in MATERIAL_COLUMNS)))
        exported["created_at"] = messages.local_created_at(raw["created_at"])
        return exported
