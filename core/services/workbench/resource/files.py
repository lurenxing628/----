"""Atomic upsert and complete scoped export, using existing resource domains."""

from typing import Union, cast

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import (
    action_row,
    check_category,
    reject_action_row,
    resource_refs,
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
        self.conn, self.kind = conn, kind
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = cast(Union[WorkbenchResourceService, WorkbenchSupplierService], self.reader.domain)
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)

    def _prepare_source(self, content, *, file_format, mode, category):
        request = import_request(self.kind, file_format, mode, category=category)
        source, notices = read_resource_file(self.kind, content, file_format)
        return PreparedImportSource.build(request, source, notices)

    def preview_import(self, content, *, file_format, mode, category):
        prepared = self._prepare_source(content, file_format=file_format, mode=mode, category=category)
        with self.tx.transaction():
            return self._prepare_import(prepared)[0]

    def _prepare_import(self, prepared):
        request = prepared.request()
        category = request["category"] if self.kind == "op_type" else None
        source, notices = prepared.parsed()
        codes = sorted({code for item in source
                        for code in (item["values"].get("business_code"),)
                        if isinstance(code, str) and code.strip()})
        preparation = self._capture_import(source, codes)
        existing = [code for code in codes if preparation.find_identity(self.kind, code) is not None]
        references = preparation.capture_references(self.repo, self.kind, existing)
        states = preparation.states(self.kind, existing)
        histories = self.repo.identity_histories(self.kind, [code for code in codes if code not in states])
        inputs = ResourceFileInput(self.reader, preparation)
        planned = [self._import_row(item, category, preparation, states, references, histories, inputs) for item in source]
        rows = [row for row, _change in planned]
        self._duplicates(rows, "business_code", source)
        if self.kind == "op_type":
            self._duplicates(rows, "label", source)
        preview = AtomicActionPreview.build(self.kind + ".import", request, rows, notices, source=prepared)
        return preview, [change for _row, change in planned]

    def _capture_import(self, source, codes):
        selected = {}
        for field, (_target, kind, _category) in RELATIONS[self.kind].items():
            for item in source:
                value = item["values"].get(field)
                selected.setdefault(kind, set()).update(code for code in (value if type(value) is list else [value])
                                                        if type(code) is str)
        names = ({"op_type": {item["values"]["label"].strip() for item in source
                              if type(item["values"].get("label")) is str}} if self.kind == "op_type" else None)
        return self.reader.preparation(codes={self.kind: set(codes)}, selected_codes=selected,
            names=names, machine_authorizations=(self.kind == "machine"))

    @staticmethod
    def _duplicates(rows, field, source):
        seen = {}
        explicit = set()
        for row, item in zip(rows, source):
            if field == "business_code":
                value = row["business_code"]
                if value is not None:
                    seen.setdefault(value, []).append(row)
                    explicit.add(value)
            else:
                raw_label = item["values"].get("label")
                file_label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None
                value = file_label or (row["before"]["label"] if row["before"] is not None else None)
                if value is not None:
                    seen.setdefault(value, []).append(row)
                    if file_label is not None:
                        explicit.add(value)
        for value, repeated in seen.items():
            if len(repeated) > 1 and value in explicit:
                numbers = ", ".join(str(row["row"]) for row in repeated)
                for row in repeated:
                    reject_action_row(row, "文件里有重复的编号或名称，这些行都没有导入：第 " + numbers + " 行。请去掉重复项后重新上传。", field=field, code="duplicate_entry")

    def _import_row(self, source, category, preparation, states, references, histories, inputs):
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        values = source["values"]
        change = None
        row["reference_fields"] = [key for key in READONLY[self.kind] if key in values]
        try:
            resource_text(values.get("business_code"), "business_code")
            code = cast(str, values["business_code"])
            row["business_code"] = code
            identity = preparation.find_identity(self.kind, code)
            if identity is None:
                raw = preparation.raw(self.kind, code)
                if raw is not None:
                    raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，这一行没有导入，资料也没有被改动。请到资料总览核对后重试。", 500)
                if code != code.strip():
                    raise ValidationError("编号不能有首尾空格，请修正后重新导入。", field="business_code")
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
                check_category(self.kind, raw, category)
            if not row["errors"]:
                row["input"], row["related"] = inputs.normalize(row["action"], code, values, row["before"], category)
                change = self.adapter.prepare(row["action"], row["input"], row["expected"]["state"], preparation)
                self._classify(row)
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "input")
        except BusinessError as exc:
            if exc.code != ErrorCode.DUPLICATE_ENTRY:
                raise
            reject_action_row(row, exc.message, code="duplicate_entry", field="label")
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
        if self.kind == "operator" and row["after"]["skills_declared"] != before["skills_declared"]:
            row["changes"]["skills_declared"] = {"before": before["skills_declared"], "after": row["after"]["skills_declared"]}
        row["result"] = "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = bool(row["changes"] and (row["related"] or row["reference_count"]
                                            or set(row["changes"]) & {"status", "default_days", "default_merge_mode", "category"}))

    def confirm_import(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("资源导入确认必须在外层工作台写事务中执行。")
        current, changes = self._prepare_import(preview.source)
        document = preview.check_current(current)
        results = []
        created_codes = []
        for row, change in zip(document["rows"], changes):
            outcome = self.adapter.apply_prepared(change, read_identity=False)
            if change.action == "create":
                created_codes.append(change.business_code)
            results.append({"row": row["row"], "result": outcome.result, **outcome.data})
        if created_codes:
            identities = self.reader.identities.active_map(self.kind, created_codes)
            for item in results:
                if item["entity_ref"] is None:
                    identity = identities.get(item["business_code"])
                    if identity is None:
                        raise RuntimeError("新增资源没有永久引用。")
                    item["entity_ref"] = identity.ref
        result = "committed" if any(row["result"] == "committed" for row in results) else "unchanged"
        return WorkbenchCommandOutcome(result, {"rows": results, "summary": document["summary"]})

    def preview_export(self, selection, *, request, selected_refs=None):
        """Export arguments holding the validated request (and any explicit refs), with their row count."""
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出预览必须在已验证的查询快照事务中执行。")
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            preparation = self.reader.preparation(refs=refs)
            for ref in refs:
                identity = preparation.identity(self.kind, ref)
                check_category(self.kind, preparation.facts.raw_record(self.kind, identity.entity_key), request.category)
            return {"request": request, "selected_refs": refs}, len(refs)
        effective = ResourcePageRequest(kind=self.kind, category=request.category) if selection == "all" else request
        matching = self.reader.matching_keys(effective)
        return {"request": effective}, len(matching)

    def export_rows(self, file_format, *, request, selected_refs=None):
        """在已验证的读快照里读完整份导出行；编码文件交给 write_export，在读事务结束后做。"""
        if not self.conn.in_transaction:
            raise RuntimeError("资源导出必须在已验证的查询快照事务中执行。")
        if selected_refs is None:
            matching = self.reader.matching_keys(request)
            check_capacity(len(matching), file_format)
            preparation = self.reader.preparation()
            identities = [preparation.identity_by_code(self.kind, code) for code in matching]
        else:
            check_capacity(len(selected_refs), file_format)
            preparation = self.reader.preparation(refs=selected_refs, machine_authorizations=(self.kind == "machine"))
            identities = [preparation.identity(self.kind, ref) for ref in selected_refs]
        return list(self._export_rows(identities, preparation))

    def write_export(self, rows, file_format, *, request):
        """只用 export_rows 读出的行生成 CSV/XLSX，不再查库，可在读事务之外调用。"""
        return write_resource_file(self.kind, rows, file_format, category=request.category)

    def _export_rows(self, identities, preparation):
        for identity in identities:
            state = preparation.export_state(self.kind, identity.entity_key)
            authorizations = preparation.authorizations(self.kind, identity.entity_key) if self.kind in ("machine", "operator") else ()
            yield flat_resource(self.kind, identity, state, authorizations)
