"""Private material upsert/import/export orchestration; no Flask or token storage.

preview_import(content: bytes, *, file_format, scope, mode='upsert') returns a
MaterialPreview. scope={} binds the material collection; filtered imports and
replace/append-only modes are unsupported by the prototype. Blank cells/columns
are omitted, \\N clears only nullable fields. Headers and escaping are documented
in material_file_codec. Existing unknown statuses may be retained, never invented.
Nonempty created_at asserts an existing timestamp; it never overwrites history.

confirm_import(preview, content, *, file_format, scope, mode='upsert') requires an
outer CommandService write transaction. Bind the original in-memory preview to
the API's temporary write context, pass preview.intent() as normalized_input,
and call confirmation from mutate. All facts/inputs are rechecked before writes;
a savepoint prevents partial batches even if the caller catches a domain failure.
Referenced updates are flagged requires_confirmation in the approved preview.

export(file_format, *, scope=None, selected_refs=None) requires the caller's
already validated read-snapshot transaction and exactly one explicit scope or
ref list. Filters export every matching row in query order; selected refs retain
their explicit order. The 2000-row import cap does not apply to either selection.
XLSX is limited only by worksheet capacity; CSV has no worksheet row/cell cap.
Returns MaterialFileDownload(filename, mime_type, content: bytes, row_count).
template(file_format='xlsx') returns header-only bytes, with XLSX field examples
in header comments (no demo records that could accidentally be imported).
"""

from __future__ import annotations

from contextlib import closing

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material import normalize_material_input
from core.models.workbench_material_file import (
    COLUMNS,
    MATERIAL_COLUMNS,
    MaterialPreview,
    check_preview,
    check_request,
    file_request,
    normalize_refs,
    normalize_scope,
    preview_row,
    reject_row,
)
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material_bulk import full_material_snapshot
from core.services.workbench.material_file_codec import check_export_capacity, read_material_file, write_material_file
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from core.services.workbench.materials import WorkbenchMaterialService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository


class WorkbenchMaterialFileService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.adapter = WorkbenchMaterialService(conn, logger=logger)
        self.query = WorkbenchMaterialQueryRepository(conn, logger=logger)
        self.repo = WorkbenchMaterialFileRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def preview_import(self, content, *, file_format, scope, mode="upsert"):
        request = file_request(content, file_format, mode, scope)
        source = read_material_file(content, file_format)
        with self.tx.transaction():
            rows = [self._import_row(item) for item in source]
            duplicates = {}
            for row in rows:
                if row["business_code"] is not None:
                    duplicates.setdefault(row["business_code"], []).append(row)
            for repeated in duplicates.values():
                if len(repeated) > 1:
                    numbers = ", ".join(str(row["row"]) for row in repeated)
                    for row in repeated:
                        reject_row(row, "同一编号在文件中重复，涉及行：" + numbers, code="duplicate_entry")
            return MaterialPreview.build("material.import", request, rows)

    def _import_row(self, source):
        row = preview_row(source["row"])
        values = source["values"]
        row["errors"] = list(source["errors"])
        try:
            code = normalize_material_input("create", {"business_code": values.get("business_code"), "label": "_"})["business_code"]
            row["business_code"] = code
            if values["business_code"] != code and self.repo.raw_material(values["business_code"]) is not None:
                raise ValidationError("原物料编号含首尾空白，不能按去空白后的编号创建或更新另一对象。", field="business_code")
            raw = self.query.get_raw(code)
            row["action"] = "create" if raw is None else "update"
            if raw is None:
                row["expected"] = {"identity": None, "material": None, "requirements": [],
                                   "identity_history": self.repo.identity_history(code)}
            else:
                identity = self.identities.get(raw["ref"]) if raw["ref"] else None
                if identity is None:
                    raise WorkbenchCommandRejected("storage_failure", "物料缺少永久引用，未自动修复。", 500)
                row["expected"] = full_material_snapshot(self.adapter, self.repo, identity)
                if code != raw["material_id"] or raw["material_id"] != raw["material_id"].strip():
                    raise ValidationError("原物料编号含首尾空白，不能安全更新。", field="business_code")
            if not row["errors"]:
                row["input"] = self._normalize_values(row["action"], code, values, raw)
                self._classify(row, raw)
        except ValidationError as exc:
            reject_row(row, exc.message, field=exc.field or "input")
        except WorkbenchCommandRejected as exc:
            reject_row(row, str(exc), code=exc.code)
        return row

    @staticmethod
    def _check_created_at(values, raw):
        if "created_at" in values and (raw is None or type(values["created_at"]) is not str
                                       or values["created_at"] != raw["created_at"]):
            raise ValidationError("创建时间是只读原始事实，不能通过导入新增或覆盖。", field="created_at")

    @staticmethod
    def _changed_input(normalized, values, raw):
        if raw is None:
            return normalized
        if "label" in normalized and values["label"] == raw["name"]:
            del normalized["label"]
        normalized["fields"] = {key: value for key, value in normalized["fields"].items() if values[key] != raw[key]}
        return normalized

    @staticmethod
    def _normalize_values(action, code, values, raw):
        WorkbenchMaterialFileService._check_created_at(values, raw)
        payload = {"fields": {key: value for key, value in values.items() if key not in ("business_code", "label", "created_at")}}
        if action == "create":
            payload["business_code"] = code
        if "label" in values:
            payload["label"] = values["label"]
        # Unedited legacy statuses are retained; a different unknown status still fails normalization.
        status = payload["fields"].get("status")
        if raw is not None and type(status) is str and status == raw["status"] and status not in ("active", "inactive"):
            del payload["fields"]["status"]
        normalized = normalize_material_input(action, payload)
        return WorkbenchMaterialFileService._changed_input(normalized, values, raw)

    @staticmethod
    def _classify(row, raw):
        if raw is None:
            row["result"] = "new"
            return
        normalized = row["input"]
        changes = dict(normalized["fields"])
        if "label" in normalized:
            changes["name"] = normalized["label"]
        row["changes"] = {key: {"before": raw[key], "after": value} for key, value in changes.items() if raw[key] != value}
        row["result"] = "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = bool(row["changes"] and row["expected"]["requirements"])

    def confirm_import(self, preview, content, *, file_format, scope, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("物料导入确认必须在外层工作台写事务中执行。")
        try:
            request = file_request(content, file_format, mode, scope)
        except (ValidationError, WorkbenchCommandRejected) as exc:
            raise WorkbenchCommandRejected("stale_write", "文件内容、模式或范围已变化，请重新预检。") from exc
        check_request(preview, "material.import", request)
        with self.tx.transaction():
            current = self.preview_import(content, file_format=file_format, scope=scope, mode=mode)
            check_preview(preview, current)
            results = []
            for row in current.as_dict()["rows"]:
                identity = row["expected"]["identity"]
                outcome = self.adapter.apply(row["action"], row["input"], WorkbenchEntityIdentity(**identity) if identity else None)
                results.append({"row": row["row"], "result": outcome.result, **outcome.data})
            result = "committed" if any(row["result"] == "committed" for row in results) else "unchanged"
            return WorkbenchCommandOutcome(result, {"rows": results, "summary": current.as_dict()["summary"]})

    def export(self, file_format, *, scope=None, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("物料导出必须在调用方已验证的查询快照事务中执行。")
        if (scope is None) == (selected_refs is None):
            raise ValidationError("导出必须明确提供筛选或选中引用，两者只能选一种。", field="scope")
        if selected_refs is None:
            query = MaterialPageRequest(**normalize_scope(scope))
            matching = WorkbenchMaterialQueryService(self.conn).matching_rows(query)
            rows, total = (self.query.get_by_ref(row["ref"]) for row in matching), len(matching)
        else:
            refs = normalize_refs(selected_refs, allow_empty=True)
            rows, total = (self.query.get_by_ref(ref) for ref in refs), len(refs)
        check_export_capacity(total, file_format)
        with closing(rows), closing(self._export_rows(rows)) as projected:
            return write_material_file(projected, file_format)

    def _export_rows(self, rows):
        for raw in rows:
            if raw is None:
                raise WorkbenchCommandRejected("entity_not_found", "选中的物料已删除，旧引用不会导出重建对象。", 404)
            identity = self.identities.get(raw["ref"]) if raw["ref"] else None
            if identity is None:
                raise WorkbenchCommandRejected("storage_failure", "导出物料缺少永久引用，未自动修补。", 500)
            self.adapter.snapshot(identity)
            yield dict(zip(COLUMNS, (raw[key] for key in MATERIAL_COLUMNS)))

    @staticmethod
    def template(file_format="xlsx"):
        return write_material_file([], file_format, template=True)
