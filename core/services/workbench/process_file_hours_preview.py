"""Linear snapshot indexing and whole-file validation for sparse hours edits."""

from collections import defaultdict
from copy import deepcopy

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import process_number, process_ref
from core.models.workbench_resource_action import action_row, reject_action_row
from core.services.workbench.process_file_hours_values import (
    HOURS_FIELDS,
    assertions,
    flat_hours,
    hours_values,
    row_key,
    supplied_values,
)
from core.services.workbench.process_projection import public_sequence, require_ref
from core.services.workbench.process_queries import _plain
from core.services.workbench.process_quota_protection import quota_skip, quota_skip_summary


def protect_hours_preview(rows, locks):
    for row in rows:
        if row["errors"] or row["input"] is None:
            continue
        ref = row["expected"]["operation_ref"]
        if ref in locks and row["expected"]["operation"]["unit_hours"] != locks[ref]["locked_unit_hours"]:
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "工艺模板的工时定额和定额已锁定的记录（来自工时校准）对不上，系统不会当成没锁定。请刷新重试；仍不行请联系维护人员。", 500)
        if ref in locks and "unit_hours" in row["changes"]:
            row.update(result="skipped", after=deepcopy(row["before"]), changes={}, requires_confirmation=False,
                       warnings=[], skip_reason=quota_skip(ref, locks[ref]))
    return quota_skip_summary(rows)


class HoursFilePreview:
    def __init__(self, facts, target_ref):
        self.facts, self.target_ref = facts, target_ref
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        self.identities = {row["ref"]: row for row in facts["identities"]}
        self.groups = {row["group_id"]: row for row in facts["groups"]}
        self.operations, self.members = defaultdict(list), defaultdict(list)
        for row in facts["operations"]:
            self.operations[(row["part_no"], row["seq"])].append(row)
            if row["status"] == "active" and row["ext_group_id"] is not None:
                self.members[row["ext_group_id"]].append(row)
        if target_ref is not None:
            process_ref(target_ref)
            target = self.identities.get(target_ref)
            if not target or not target["active"] or target["kind"] != "part":
                raise WorkbenchCommandRejected("entity_not_found", "这个零件已失效。请返回列表重新选择。", 404)

    def identity(self, row, kind, key):
        ref = require_ref(row["ref"], "工艺")
        current = self.identities.get(ref)
        if not current or not current["active"] or current["kind"] != kind or current["entity_key"] != str(key):
            raise WorkbenchCommandRejected("storage_failure", "工艺编号和原记录对不上，系统不会替你改资料。请刷新重试；仍不行请联系维护人员。", 500)
        return ref

    def resolve(self, values):
        code, sequence = row_key(values)
        part = self.parts.get(code)
        if part is None:
            raise ValidationError("这个图号不存在，工时导入不会新增零件。请先到基础资料新增零件。", field="business_code")
        part_ref = self.identity(part, "part", code)
        if self.target_ref is not None and self.target_ref != part_ref:
            raise ValidationError("这一行不属于当前零件。请只导入当前零件的工序。", field="business_code")
        found = self.operations.get((code, sequence), [])
        if len(found) != 1 or found[0]["status"] != "active":
            raise ValidationError("这道工序不存在、已停用或有重复，系统不会新增、恢复或猜着对应。请到基础资料核对工序。", field="sequence")
        operation = found[0]
        self.identity(operation, "template_operation", operation["id"])
        return part_ref, operation

    def group(self, operation):
        key = operation["ext_group_id"]
        if key is None:
            return None
        group = self.groups.get(key)
        if group is None or group["part_no"] != operation["part_no"]:
            raise WorkbenchCommandRejected("group_invalid", "这道工序原来的外协组关系缺失或跨了零件，系统不会解除或替你改。请到基础资料核对外协组。", 422)
        self.identity(group, "template_external_group", key)
        if group["merge_mode"] not in ("separate", "merged"):
            raise WorkbenchCommandRejected("group_invalid", "原外协组用哪种周期算法说不清。请到基础资料核对外协组。", 422)
        start, end = group["start_seq"], group["end_seq"]
        if type(start) is not int or type(end) is not int or not 0 < start <= end:
            raise WorkbenchCommandRejected("group_invalid", "原外协组的工序范围不合法，这次没有改动。请到基础资料核对外协组起止序。", 422)
        return group

    def source_ready(self, operation):
        state = self.facts["workflow"][operation["part_no"]]
        confirmation = state["operations"].get(operation["ref"], {}).get("source", {})
        if (state["workflow"]["route"]["state"] != "confirmed" or confirmation.get("state") != "confirmed"
                or operation["source"] not in ("internal", "external")):
            raise WorkbenchCommandRejected("stage_not_ready", "目标工序的归属尚未确认或已过期，请先核对归属。", 422)

    def row(self, decoded):
        row = action_row(decoded["row"], action="update")
        row["errors"] = deepcopy(decoded["errors"])
        try:
            values = supplied_values(decoded["values"])
            code, sequence = row_key(values)
            row.update(business_code=code, sequence=public_sequence(sequence))
            part_ref, operation = self.resolve(values)
            group = self.group(operation)
            row.update(entity_ref=part_ref, before=flat_hours(operation, group),
                       expected={"part_ref": part_ref, "operation_ref": operation["ref"], "operation": _plain(deepcopy(operation)),
                                 "group": _plain(deepcopy(group))})
            self.source_ready(operation)
            assertions(values, operation, group)
            updates = hours_values(values, operation, group)
            row["input"] = {"values": deepcopy(values), "hours": updates}
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "input")
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code)
        return row

    @staticmethod
    def duplicates(rows):
        entries = defaultdict(list)
        for row in rows:
            if row["business_code"] is not None and "sequence" in row:
                entries[(row["business_code"], row["sequence"])].append(row)
        for repeated in entries.values():
            if len(repeated) > 1:
                for row in repeated:
                    if not any(error["code"] == "duplicate_entry" for error in row["errors"]):
                        reject_action_row(row, "同一图号和工序在文件中重复，这批不能写入。请合并重复行后重新导入。", field="sequence", code="duplicate_entry")

    def group_values(self, rows):
        entries, proposals = defaultdict(list), {}
        for row in rows:
            group = row["expected"]["group"] if row["expected"] else None
            if group is not None:
                entries[group["group_id"]].append(row)
        for key, related in entries.items():
            supplied = [row["input"]["hours"]["group_total_days"] for row in related
                        if row["input"] and "group_total_days" in row["input"]["hours"]]
            if not supplied:
                continue
            if any(value != supplied[0] for value in supplied[1:]):
                for row in related:
                    reject_action_row(row, "同一个合并组的周期在文件中不一致，这批不能写入。请统一后重新导入。",
                                      field="group_total_days", code="group_value_conflict")
                continue
            group = self.groups[key]
            if not self.valid_members(group):
                for row in related:
                    reject_action_row(row, "合并组里有不合法的成员，工时导入不能改它的关系。请到基础资料核对外协组。", code="group_invalid")
                continue
            proposals[key] = supplied[0]
        return proposals

    def valid_members(self, group):
        return all(member["part_no"] == group["part_no"] and member["source"] == "external"
                   and type(member["seq"]) is int and group["start_seq"] <= member["seq"] <= group["end_seq"]
                   for member in self.members[group["group_id"]])

    @staticmethod
    def finish(row, proposals):
        if row["input"] is None:
            return
        group, updates = row["expected"]["group"], row["input"]["hours"]
        after = dict(row["before"])
        after.update(updates)
        if group is not None and group["group_id"] in proposals:
            after["group_total_days"] = proposals[group["group_id"]]
        row["after"] = after
        # A merged member may clear its own cycle only with a valid effective total.
        if "external_days" in updates and updates["external_days"] is None:
            try:
                process_number(after["group_total_days"], positive=True)
            except WorkbenchCommandRejected as exc:
                reject_action_row(row, str(exc), field="group_total_days")
        row["changes"] = {key: {"before": row["before"][key], "after": after[key]} for key in HOURS_FIELDS
                          if row["before"][key] != after[key]}
        if row["errors"]:
            return
        row["result"] = "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = after["source"] == "internal" and after["unit_hours"] == 0
        if row["requires_confirmation"]:
            row["warnings"] = [{"row": row["row"], "field": "unit_hours", "code": "zero_unit_hours_review",
                                "message": "单件工时是 0，请明确复核；导入不会把工时阶段标成已确认。"}]

    def build(self, decoded_rows):
        rows = [self.row(decoded) for decoded in decoded_rows]
        self.duplicates(rows)
        proposals = self.group_values(rows)
        for row in rows:
            self.finish(row, proposals)
        return rows, {"affected_groups": [], "zero_review_required": any(row["requires_confirmation"] for row in rows)}
