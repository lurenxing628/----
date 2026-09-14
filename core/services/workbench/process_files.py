"""Atomic process-file commands bound to the original bytes and full read facts."""

import hashlib

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_process_file import check_format, file_columns
from core.models.workbench_resource_action import ResourceActionPreview, check_resource_preview, resource_refs

from .process_file_codec import decode_process_file
from .process_queries import WorkbenchProcessQueryService
from .process_quota_protection import quota_skip_summary


def file_operation(kind):
    file_columns(kind)
    return "process_" + kind + "_import.confirm"


def _hours_result_rows(rows):
    # Public file results keep their existing enum; explicit skip evidence is separate.
    skipped = quota_skip_summary(rows)
    return [{**row, "result": "unchanged"} if row["result"] == "skipped" else row for row in rows], skipped


class WorkbenchProcessFileService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn, self.logger = conn, logger
        self.reader = reader or WorkbenchProcessQueryService(conn, logger)

    def _domain(self, kind):
        file_columns(kind)
        if kind == "route":
            from .process_file_route import ProcessRouteFileOperations

            return ProcessRouteFileOperations(self.conn, self.logger)
        from .process_file_hours import ProcessHoursFileOperations

        return ProcessHoursFileOperations(self.conn, self.logger)

    def preview_import(self, kind, content, *, file_format, mode="upsert", target_ref=None):
        file_columns(kind)
        check_format(file_format)
        if mode != "upsert":
            raise WorkbenchCommandRejected("invalid_input", "工艺文件仅支持按图号增量导入。", 400)
        decoded = decode_process_file(kind, content, file_format)
        with self.reader.read_snapshot() as state:
            if target_ref is not None:
                self.reader.resolve(target_ref)
            rows, extra = self._domain(kind).preview_rows(decoded, self.reader.facts(), target_ref)
            if kind == "hours":
                rows, skipped = _hours_result_rows(rows)
                extra.update(skipped)
            for row in rows:
                row.setdefault("route_summary", None)
            request = {"kind": kind, "scope": {}, "target_ref": target_ref, "format": file_format, "mode": mode,
                       "file_sha256": hashlib.sha256(content).hexdigest(), "state": state,
                       "acknowledgements": {"discard_group_refs": sorted(group["ref"] for group in extra["affected_groups"]),
                                            "zero_review_required": extra["zero_review_required"]}}
            return ResourceActionPreview.build(file_operation(kind), request, rows), extra

    def confirm_import(self, preview, content, *, discard_group_refs, confirm_zero_unit_hours):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺文件确认必须位于外层命令与回执事务中。")
        if not isinstance(preview, ResourceActionPreview):
            raise WorkbenchCommandRejected("stale_write", "原文件预检不存在，请重新预检。")
        refs = resource_refs(discard_group_refs, allow_empty=True)
        if type(confirm_zero_unit_hours) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "请明确是否已复核零工时。", 400)
        original = preview.as_dict()["request"]
        with TransactionManager(self.conn).transaction():
            current, extra = self.preview_import(original["kind"], content, file_format=original["format"],
                                                 mode=original["mode"], target_ref=original["target_ref"])
            check_resource_preview(preview, current)
            if set(refs) != {group["ref"] for group in extra["affected_groups"]}:
                raise WorkbenchCommandRejected("group_discard_required", "请逐项核对全部受影响外协组，不能漏选或多选。")
            if extra["zero_review_required"] and not confirm_zero_unit_hours:
                raise WorkbenchCommandRejected("zero_review_required", "有单件工时是 0 的记录。请逐条复核并勾选确认后再导入。")
            body = current.as_dict()
            rows, affected_refs = self._domain(original["kind"]).apply_rows(
                body["rows"], discard_group_refs=refs, confirm_zero_unit_hours=confirm_zero_unit_hours)
            data = {"kind": original["kind"], "rows": rows, "summary": body["summary"], "affected_refs": affected_refs}
            if original["kind"] == "hours":
                rows, skipped = _hours_result_rows(rows)
                data.update(skipped)
                data["rows"] = rows
                # This is the existing refresh set, not a count of business changes.
                data["affected_refs"] = sorted({row["entity_ref"] for row in rows})
                data["summary"] = {**body["summary"], "update": sum(row["result"] == "committed" for row in rows),
                                   "unchanged": sum(row["result"] == "unchanged" for row in rows)}
            unchanged = all(row["result"] == "unchanged" for row in rows)
            return WorkbenchCommandOutcome("unchanged" if unchanged else "committed", data)
