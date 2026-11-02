"""Atomic process-file commands bound to the retained parsed source and full read facts."""

from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import resource_refs
from core.models.workbench_resource_file_source import PreparedImportSource

from .file_codec import decode_process_file
from .queries import WorkbenchProcessQueryService


def file_operation(kind):
    return "process_" + kind + "_import.confirm"


class WorkbenchProcessFileService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.reader = WorkbenchProcessQueryService(conn, logger)

    def _domain(self, kind):
        if kind == "route":
            from .file_route import ProcessRouteFileOperations

            return ProcessRouteFileOperations(self.conn, self.logger)
        from .file_hours import ProcessHoursFileOperations

        return ProcessHoursFileOperations(self.conn, self.logger)

    def _prepare_source(self, kind, content, *, file_format, mode, target_ref):
        decoded, notices = decode_process_file(kind, content, file_format)
        request = {"kind": kind, "scope": {}, "target_ref": target_ref, "format": file_format, "mode": mode}
        return PreparedImportSource.build(request, decoded, notices)

    def preview_import(self, kind, content, *, file_format, mode, target_ref):
        prepared = self._prepare_source(kind, content, file_format=file_format, mode=mode, target_ref=target_ref)
        preview, extra, _, _ = self._prepare_import(prepared)
        return preview, extra

    def _prepare_import(self, prepared):
        request = prepared.request()
        kind, target_ref = request["kind"], request["target_ref"]
        decoded, notices = prepared.parsed()
        reader = (WorkbenchProcessQueryService(self.conn, self.logger, part_ref=target_ref)
                  if target_ref is not None else self.reader)
        with reader.read_snapshot() as state:
            if target_ref is not None:
                reader.identity_of(target_ref)
            domain = self._domain(kind)
            facts = reader.raw_facts() if kind == "route" else reader.facts()
            rows, extra = domain.preview_rows(decoded, facts, target_ref)
            for row in rows:
                row.setdefault("route_summary", None)
            request.update(state=state, acknowledgements={
                "discard_group_refs": sorted(group["ref"] for group in extra["affected_groups"]),
                "zero_review_required": extra["zero_review_required"]})
            return AtomicActionPreview.build(file_operation(kind), request, rows, notices, source=prepared), extra, domain, rows

    def confirm_import(self, preview, *, discard_group_refs, confirm_zero_unit_hours):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺文件确认必须位于外层命令与回执事务中。")
        refs = resource_refs(discard_group_refs, allow_empty=True)
        if type(confirm_zero_unit_hours) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "请明确是否已复核零工时。", 400)
        current, extra, domain, prepared_rows = self._prepare_import(preview.source)
        body = preview.check_current(current)
        kind = body["request"]["kind"]
        if set(refs) != {group["ref"] for group in extra["affected_groups"]}:
            raise WorkbenchCommandRejected("group_discard_required", "请逐项核对全部受影响外协组，不能漏选或多选。")
        if extra["zero_review_required"] and not confirm_zero_unit_hours:
            raise WorkbenchCommandRejected("zero_review_required", "单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。请按 0 导入。")
        rows, affected_refs = domain.apply_rows(prepared_rows)
        data = {"kind": kind, "rows": rows, "summary": body["summary"], "affected_refs": affected_refs}
        unchanged = all(row["result"] == "unchanged" for row in rows)
        return WorkbenchCommandOutcome("unchanged" if unchanged else "committed", data)
