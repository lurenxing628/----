"""Atomic process-file commands bound to the original bytes and full read facts."""

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_process_file import check_format, file_columns
from core.models.workbench_resource_action import ResourceActionPreview, check_resource_preview, resource_refs
from core.models.workbench_resource_file_source import PreparedImportSource

from .file_codec import decode_process_file
from .queries import WorkbenchProcessQueryService


def file_operation(kind):
    file_columns(kind)
    return "process_" + kind + "_import.confirm"


class WorkbenchProcessFileService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn, self.logger = conn, logger
        self.reader = reader or WorkbenchProcessQueryService(conn, logger)

    def _domain(self, kind):
        file_columns(kind)
        if kind == "route":
            from .file_route import ProcessRouteFileOperations

            return ProcessRouteFileOperations(self.conn, self.logger)
        from .file_hours import ProcessHoursFileOperations

        return ProcessHoursFileOperations(self.conn, self.logger)

    def _prepare_source(self, kind, content, *, file_format, mode, target_ref):
        file_columns(kind)
        check_format(file_format)
        if mode != "upsert":
            raise WorkbenchCommandRejected("invalid_input", "工艺文件仅支持按图号增量导入。", 400)
        decoded, notices = decode_process_file(kind, content, file_format)
        request = {"kind": kind, "scope": {}, "target_ref": target_ref, "format": file_format, "mode": mode}
        prepared = PreparedImportSource.build(file_operation(kind), request, decoded, notices, content=content)
        return prepared, dict(request, actual_source_ref=prepared.source_ref)

    def preview_import(self, kind, content, *, file_format, mode="upsert", target_ref=None):
        prepared, request = self._prepare_source(kind, content, file_format=file_format, mode=mode, target_ref=target_ref)
        preview, extra, _, _ = self._prepare_import(kind, prepared, request)
        return preview, extra

    def _prepare_import(self, kind, prepared, request):
        decoded, notices = prepared.parsed()
        target_ref = request["target_ref"]
        if target_ref is not None and (not isinstance(target_ref, str) or len(target_ref) != 48
                                       or any(c not in "0123456789abcdef" for c in target_ref)):
            raise WorkbenchCommandRejected("entity_not_found", "零件记录不存在，请返回列表重新选择。", 404)
        reader = (WorkbenchProcessQueryService(self.conn, self.logger, part_ref=target_ref)
                  if target_ref is not None and self.reader.repo.part_ref != target_ref else self.reader)
        with reader.read_snapshot() as state:
            if target_ref is not None:
                reader.resolve(target_ref)
            domain = self._domain(kind)
            rows, extra = domain.preview_rows(decoded, reader.facts(), target_ref)
            for row in rows:
                row.setdefault("route_summary", None)
            request.update(state=state, acknowledgements={
                "discard_group_refs": sorted(group["ref"] for group in extra["affected_groups"]),
                "zero_review_required": extra["zero_review_required"]})
            return ResourceActionPreview.build(file_operation(kind), request, rows, notices, source=prepared), extra, domain, rows

    def confirm_import(self, preview, content, *, discard_group_refs, confirm_zero_unit_hours):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺文件确认必须位于外层命令与回执事务中。")
        if not isinstance(preview, ResourceActionPreview):
            raise WorkbenchCommandRejected("stale_write", "原文件预检不存在，请重新预检。")
        refs = resource_refs(discard_group_refs, allow_empty=True)
        if type(confirm_zero_unit_hours) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "请明确是否已复核零工时。", 400)
        original = preview.as_dict()["request"]
        source = PreparedImportSource.confirmation(preview, content)
        request = source.request_for(file_operation(original["kind"]), original["format"], original["mode"])
        current, extra, domain, prepared_rows = self._prepare_import(original["kind"], source, request)
        check_resource_preview(preview, current)
        if set(refs) != {group["ref"] for group in extra["affected_groups"]}:
            raise WorkbenchCommandRejected("group_discard_required", "请逐项核对全部受影响外协组，不能漏选或多选。")
        if extra["zero_review_required"] and not confirm_zero_unit_hours:
            raise WorkbenchCommandRejected("zero_review_required", "单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。请按 0 导入。")
        rows, affected_refs = domain.apply_rows(prepared_rows)
        summary = {key: sum(row["result"] == key for row in prepared_rows)
                   for key in ("new", "update", "unchanged", "delete", "rejected")}
        data = {"kind": original["kind"], "rows": rows, "summary": summary, "affected_refs": affected_refs}
        unchanged = all(row["result"] == "unchanged" for row in rows)
        return WorkbenchCommandOutcome("unchanged" if unchanged else "committed", data)
