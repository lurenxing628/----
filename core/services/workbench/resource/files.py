"""Atomic upsert and complete scoped export, using existing resource domains."""

from contextlib import closing
from typing import Union, cast

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
from core.models.workbench_resource_file import READONLY, RELATIONS, WRITABLE, import_request
from core.models.workbench_resource_file_source import PreparedImportSource
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.facts.file_codec import read_resource_file
from core.services.workbench.facts.file_writer import check_capacity, write_resource_file
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from .entities import WorkbenchResourceService
from .file_input import ResourceFileInput, proposed_fields, same_value
from .file_projection import flat_resource, reference_count
from .queries import WorkbenchResourceQueryService
from .suppliers import WorkbenchSupplierService


class WorkbenchResourceFileService:
    def __init__(self, conn, kind, logger=None, reader=None):
        self.conn, self.kind = conn, action_kind(kind)
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = cast(Union[WorkbenchResourceService, WorkbenchSupplierService], self.reader.domain)
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)

    def prepare_import(self, content, *, file_format, scope, mode="upsert"):
        return self._prepare_source(content, file_format=file_format, scope=scope, mode=mode)[0]

    def _prepare_source(self, content, *, file_format, scope, mode):
        request = import_request(self.kind, content, file_format, mode, scope)
        source, notices = read_resource_file(self.kind, content, file_format)
        prepared = PreparedImportSource.build(self.kind + ".import", request, source, notices, content=content)
        request["actual_source_ref"] = prepared.source_ref
        return prepared, request

    def preview_import(self, content, *, file_format, scope, mode="upsert"):
        return self._prepare_import(content, file_format=file_format, scope=scope, mode=mode)[0]

    def _prepare_import(self, content, *, file_format, scope, mode="upsert"):
        if isinstance(content, PreparedImportSource):
            prepared = content
            request = prepared.request_for(self.kind + ".import", file_format, mode, resource_scope(self.kind, scope))
        else:
            prepared, request = self._prepare_source(content, file_format=file_format, scope=scope, mode=mode)
        source, notices = prepared.parsed()
        with self.tx.transaction():
            codes = sorted({item["values"]["business_code"].strip() for item in source
                            if isinstance(item["values"].get("business_code"), str)})
            preparation = self._capture_import(source, codes)
            existing = [code for code in codes if preparation.find_identity(self.kind, code) is not None]
            references = preparation.capture_references(self.repo, self.kind, existing)
            states = preparation.states(self.kind, existing)
            histories = self.repo.identity_histories(self.kind, [code for code in codes if code not in states])
            inputs = ResourceFileInput(self.reader, preparation)
            planned = [self._import_row(item, request["scope"], preparation, states, references, histories, inputs) for item in source]
            rows = [row for row, _change in planned]
            self._duplicates(rows, "business_code")
            if self.kind == "op_type":
                self._duplicates(rows, "label")
            preview = ResourceActionPreview.build(self.kind + ".import", request, rows, notices, source=prepared)
            return preview, [change for _row, change in planned]

    def _capture_import(self, source, codes):
        original = {item["values"]["business_code"] for item in source
                    if type(item["values"].get("business_code")) is str}
        selected = {}
        for field, (_target, kind, _category) in RELATIONS[self.kind].items():
            for item in source:
                value = item["values"].get(field)
                selected.setdefault(kind, set()).update(code for code in (value if type(value) is list else [value])
                                                        if type(code) is str)
        labels = {item["values"]["label"].strip() for item in source if type(item["values"].get("label")) is str}
        return self.reader.preparation(codes={self.kind: set(codes) | original}, selected_codes=selected,
            names={"op_type": labels} if self.kind == "op_type" else None, machine_authorizations=True)

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

    def _import_row(self, source, scope, preparation, states, references, histories, inputs):
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        values = source["values"]
        change = None
        row["reference_fields"] = [key for key in READONLY[self.kind] if key in values]
        try:
            code = cast(str, resource_text(values.get("business_code"), "business_code"))
            row["business_code"] = code
            if values["business_code"] != code and preparation.raw(self.kind, values["business_code"]) is not None:
                raise ValidationError("编号不能有首尾空格，请修正后重新导入。", field="business_code")
            identity = preparation.find_identity(self.kind, code)
            if identity is None:
                raw = preparation.raw(self.kind, code)
                if raw is not None:
                    raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，这一行没有导入，资料也没有被改动。请到资料总览核对后重试。", 500)
                row["action"] = "create"
                row["expected"] = {"state": None, "history": histories[code]}
            else:
                row["action"] = "update"
                state = states[code]
                raw = state["supplier"] if self.kind == "supplier" else state["record"]
                expected = {"state": state, "references": references[code]}
                authorizations = preparation.authorizations(self.kind, code) if self.kind in ("machine", "operator") else ()
                row.update(entity_ref=identity.ref, expected=expected,
                           before=flat_resource(self.kind, identity, state, authorizations), reference_count=reference_count(expected))
                check_category(self.kind, raw, scope)
            if not row["errors"]:
                row["input"], row["related"] = inputs.normalize(row["action"], code, values, row["before"], scope)
                change = self.adapter.prepare(row["action"], row["input"], row["expected"]["state"], preparation)
                self._classify(row)
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "input")
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code)
        return row, change

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
                current, changes = self._prepare_import(PreparedImportSource.confirmation(preview, content), file_format=file_format, scope=scope, mode=mode)
            except ValidationError as exc:
                raise WorkbenchCommandRejected("stale_write", "文件或导入范围已经变了，没有导入。请点「重新预检」后再确认。") from exc
            check_resource_preview(preview, current)
            results = []
            document = current.as_dict()
            for row, change in zip(document["rows"], changes):
                outcome = self.adapter.apply_prepared(change)
                results.append({"row": row["row"], "result": outcome.result, **outcome.data})
            result = "committed" if any(row["result"] == "committed" for row in results) else "unchanged"
            return WorkbenchCommandOutcome(result, {"rows": results, "summary": document["summary"]})

    def preview_export(self, selection, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出预览必须在已验证的查询快照事务中执行。")
        if selection not in ("all", "filtered", "selected") or (selection != "selected" and selected_refs is not None):
            raise WorkbenchCommandRejected("invalid_input", "导出前要先选清楚是全部、当前筛选还是勾选的记录，没有开始下载。请重新选择导出范围。", 400)
        scope = resource_scope(self.kind, scope)
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            preparation = self.reader.preparation()
            for ref in refs:
                identity = preparation.identity(self.kind, ref)
                check_category(self.kind, preparation.facts.raw_record(self.kind, identity.entity_key), scope)
            return {"scope": scope, "selected_refs": refs}, len(refs)
        effective = resource_scope(self.kind, {"category": scope["category"]}) if selection == "all" else scope
        count = len(self.reader.matching_keys(ResourcePageRequest(kind=self.kind, **effective)))
        return {"scope": effective}, count

    def export_rows(self, file_format, *, scope, selected_refs=None):
        """在已验证的读快照里读完整份导出行；编码文件交给 write_export，在读事务结束后做。"""
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出必须在已验证的查询快照事务中执行。")
        scope = resource_scope(self.kind, scope)
        preparation = self.reader.preparation()
        if selected_refs is None:
            query = ResourcePageRequest(kind=self.kind, **scope)
            index = (self.reader.table_index(query) if self.reader._table_indexes is not None else
                     preparation.facts.index(query, self.reader.repo.toolbar_keys(query)))
            matching = index.matching_keys(query)
            rows, count = (index.rows[code] for code in matching), len(matching)
        else:
            refs = resource_refs(selected_refs, allow_empty=True)
            rows, count = ({"ref": ref} for ref in refs), len(refs)
        with closing(rows):
            check_capacity(count, file_format)
            return list(self._export_rows(rows, scope, preparation))

    def write_export(self, rows, file_format, *, scope):
        """只用 export_rows 读出的行生成 CSV/XLSX，不再查库，可在读事务之外调用。"""
        return write_resource_file(self.kind, rows, file_format, category=resource_scope(self.kind, scope)["category"])

    def _export_rows(self, rows, scope, preparation):
        for row in rows:
            if row["ref"] is None:
                raise WorkbenchCommandRejected("storage_failure", "有资源在资料里查不到编号，请到资料总览核对后重试。", 500)
            identity = preparation.identity(self.kind, row["ref"])
            state = preparation.export_state(self.kind, identity.entity_key)
            authorizations = preparation.authorizations(self.kind, identity.entity_key) if self.kind in ("machine", "operator") else ()
            flat = flat_resource(self.kind, identity, state, authorizations)
            check_category(self.kind, flat, scope)
            yield flat

    @staticmethod
    def template(kind, file_format="xlsx", *, category=None):
        action_kind(kind)
        if (kind == "op_type" and category not in ("internal", "external")) or (kind != "op_type" and category is not None):
            raise ValidationError("下载工种模板要先选自制还是外协，没有开始下载。请选好归属后重试。", field="category")
        return write_resource_file(kind, [], file_format, template=True, category=category)
