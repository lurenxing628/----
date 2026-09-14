"""Atomic upsert and complete scoped export, using existing resource domains."""

from contextlib import closing
from typing import cast

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import (
    ResourceActionPreview,
    action_kind,
    action_row,
    check_category,
    check_resource_preview,
    reject_action_row,
    resource_refs,
    resource_scope,
)
from core.models.workbench_resource_file import WRITABLE, import_request
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.resource_file_codec import read_resource_file
from core.services.workbench.resource_file_input import ResourceFileInput, proposed_fields, same_value
from core.services.workbench.resource_file_projection import flat_resource, reference_count, resource_file_state
from core.services.workbench.resource_file_writer import check_capacity, write_resource_file
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository


class WorkbenchResourceFileService:
    def __init__(self, conn, kind, logger=None):
        self.conn, self.kind = conn, action_kind(kind)
        self.reader = WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = self.reader.domain
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.inputs = ResourceFileInput(self.reader, self.repo)
        self.tx = TransactionManager(conn)

    def preview_import(self, content, *, file_format, scope, mode="upsert"):
        request = import_request(self.kind, content, file_format, mode, scope)
        source = read_resource_file(self.kind, content, file_format)
        with self.tx.transaction():
            rows = [self._import_row(item, request["scope"]) for item in source]
            self._duplicates(rows, "business_code")
            if self.kind == "op_type":
                self._duplicates(rows, "label")
            return ResourceActionPreview.build(self.kind + ".import", request, rows)

    @staticmethod
    def _duplicates(rows, field):
        seen = {}
        for row in rows:
            value = row["business_code"] if field == "business_code" else (row["input"] or {}).get("label")
            if value is not None:
                seen.setdefault(value, []).append(row)
        for repeated in seen.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(row["row"]) for row in repeated)
                for row in repeated:
                    reject_action_row(row, "文件里有重复的编号或名称，这些行都没有导入：第 " + numbers + " 行。请去掉重复项后重新上传。", field=field, code="duplicate_entry")

    def _import_row(self, source, scope):
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        values = source["values"]
        try:
            code = cast(str, resource_text(values.get("business_code"), "business_code"))
            row["business_code"] = code
            if values["business_code"] != code and self.repo.raw(self.kind, values["business_code"]) is not None:
                raise ValidationError("这个编号前后带空格，这一行没有导入，系统不会猜成另一个编号。请去掉前后的空格。", field="business_code")
            raw = self.repo.raw(self.kind, code)
            row["action"] = "create" if raw is None else "update"
            if raw is None:
                row["expected"] = {"state": None, "history": self.repo.identity_history(self.kind, code)}
            else:
                identity = self.reader.identities.find_active(self.kind, code)
                if identity is None:
                    raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，这一行没有导入，资料也没有被改动。请到资料总览核对后重试。", 500)
                expected = resource_file_state(self.reader, self.repo, identity)
                row.update(entity_ref=identity.ref, expected=expected,
                           before=flat_resource(self.kind, identity, expected, self.repo), reference_count=reference_count(expected))
                check_category(self.kind, raw, scope)
            if not row["errors"]:
                row["input"], row["related"] = self.inputs.normalize(row["action"], code, values, row["before"], scope)
                self._classify(row)
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "input")
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code)
        return row

    def _classify(self, row):
        before, payload = row["before"], row["input"]
        row["after"] = proposed_fields(self.kind, row["business_code"], before, payload, row["related"])
        if before is None:
            row["result"] = "new"
            return
        row["changes"] = {key: {"before": before[key], "after": row["after"][key]} for key in WRITABLE[self.kind]
                          if key in row["after"] and not same_value(before[key], row["after"][key], key)}
        if self.kind == "operator" and row["after"].get("skills_declared") != before["skills_declared"]:
            row["changes"]["skills_declared"] = {"before": before["skills_declared"], "after": row["after"]["skills_declared"]}
        row["result"] = "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = bool(row["changes"] and (row["related"] or row["reference_count"]
                                            or set(row["changes"]) & {"status", "default_days", "default_merge_mode", "category"}))

    def confirm_import(self, preview, content, *, file_format, scope, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("资源导入确认必须在外层工作台写事务中执行。")
        with self.tx.transaction():
            try:
                current = self.preview_import(content, file_format=file_format, scope=scope, mode=mode)
            except ValidationError as exc:
                raise WorkbenchCommandRejected("stale_write", "文件或导入范围已经变了，没有导入。请重新点「预检」后再确认。") from exc
            check_resource_preview(preview, current)
            results = []
            for row in current.as_dict()["rows"]:
                identity = self.reader.resolve(row["entity_ref"]) if row["entity_ref"] else None
                outcome = self.adapter.apply(row["action"], row["input"], identity)
                results.append({"row": row["row"], "result": outcome.result, **outcome.data})
            result = "committed" if any(row["result"] == "committed" for row in results) else "unchanged"
            return WorkbenchCommandOutcome(result, {"rows": results, "summary": current.as_dict()["summary"]})

    def preview_export(self, selection, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出预览必须在已验证的查询快照事务中执行。")
        if selection not in ("all", "filtered", "selected") or (selection != "selected" and selected_refs is not None):
            raise WorkbenchCommandRejected("invalid_input", "导出前要先选清楚是全部、当前筛选还是勾选的记录，没有开始下载。请重新选择导出范围。", 400)
        scope = resource_scope(self.kind, scope)
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            for ref in refs:
                identity = self.reader.resolve(ref)
                check_category(self.kind, self.repo.raw(self.kind, identity.entity_key), scope)
            return {"scope": scope, "selected_refs": refs}, len(refs)
        effective = resource_scope(self.kind, {"category": scope["category"]}) if selection == "all" else scope
        count = len(self.reader.matching_keys(ResourcePageRequest(kind=self.kind, **effective)))
        return {"scope": effective}, count

    def export(self, file_format, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出必须在已验证的查询快照事务中执行。")
        scope = resource_scope(self.kind, scope)
        if selected_refs is None:
            matching = self.reader.matching_rows(ResourcePageRequest(kind=self.kind, **scope))
            rows, count = (row for row in matching), len(matching)
        else:
            refs = resource_refs(selected_refs, allow_empty=True)
            rows, count = ({"ref": ref} for ref in refs), len(refs)
        with closing(rows):
            check_capacity(count, file_format)
            return write_resource_file(self.kind, self._export_rows(rows, scope), file_format, category=scope["category"])

    def _export_rows(self, rows, scope):
        for row in rows:
            if row["ref"] is None:
                raise WorkbenchCommandRejected("storage_failure", "有资源在资料里查不到编号，没有开始下载，资料也没有被改动。请到资料总览核对后重试。", 500)
            identity = self.reader.resolve(row["ref"])
            state = resource_file_state(self.reader, self.repo, identity)
            flat = flat_resource(self.kind, identity, state, self.repo)
            check_category(self.kind, flat, scope)
            yield flat

    @staticmethod
    def template(kind, file_format="xlsx", *, category=None):
        action_kind(kind)
        if (kind == "op_type" and category not in ("internal", "external")) or (kind != "op_type" and category is not None):
            raise ValidationError("下载工种模板要先选自制还是外协，没有开始下载。请选好归属后重试。", field="category")
        return write_resource_file(kind, [], file_format, template=True, category=category)
