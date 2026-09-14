"""Snapshot-only route-file preparation; only parser references need database reads."""

from collections import defaultdict
from copy import deepcopy

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import COLUMNS
from core.models.workbench_resource_action import action_row, reject_action_row
from core.models.workbench_resource_input import resource_object, resource_text
from core.services.workbench.process_file_values import typed_value
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from core.services.workbench.process_projection import project_group, public_sequence, require_ref
from core.services.workbench.process_route_apply import affected_group_rows
from core.services.workbench.process_route_preview import ProcessRoutePreviewService


def canonical_part(part):
    return {"business_code": part["part_no"], "label": part["part_name"],
            "route_raw": part["route_raw"], "remark": part["remark"]}


def reject_duplicates(rows):
    occurrences = defaultdict(list)
    for row in rows:
        if row["business_code"] is not None:
            occurrences[row["business_code"]].append(row)
    for repeated in occurrences.values():
        if len(repeated) > 1:
            for row in repeated:
                if not any(error["code"] == "duplicate_entry" for error in row["errors"]):
                    reject_action_row(row, "同一图号在文件中重复，这批不能导入。请合并重复行后重新导入。",
                                      field="business_code", code="duplicate_entry")


def _changed_sequences(operations, preview):
    # Match prepare_route's preserving diff, sharing one parser snapshot per file.
    existing = {row["seq"]: row for row in operations}
    incoming = {row["sequence"]: row for row in preview["operations"]}
    changed = {seq for seq, row in existing.items() if row["status"] == "active" and
               (seq not in incoming or row["op_type_name"] != incoming[seq]["op_type_name"])}
    changed.update(seq for seq in incoming if seq not in existing or existing[seq]["status"] != "active")
    return changed


def _route_summary(preview):
    diagnostics = [{**row, **({"sequence": public_sequence(row["sequence"])} if "sequence" in row else {})}
                   for row in preview["diagnostics"]]
    return {"counts": dict(preview["counts"]), "diagnostics": diagnostics,
            "can_confirm_route": preview["can_confirm_route"]}


class RouteFilePreview:
    def __init__(self, conn, logger, facts, target_ref, stack):
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        self.identities = {row["ref"]: row for row in facts["identities"]}
        self.operations, self.groups = defaultdict(list), defaultdict(list)
        owners = {row["group_id"]: row["part_no"] for row in facts["groups"]}
        self.foreign_members = set()
        for row in facts["operations"]:
            self.operations[row["part_no"]].append(row)
            owner = owners.get(row["ext_group_id"])
            if owner is not None and owner != row["part_no"]:
                self.foreign_members.add(owner)
        for row in facts["groups"]:
            self.groups[row["part_no"]].append(row)
        self.target_ref, self.stack = target_ref, stack
        self.parser = ProcessRoutePreviewService(conn, logger)
        self.parser_ready = False

    def row(self, source):
        row = action_row(source["row"])
        row.update(errors=deepcopy(source["errors"]), related={"route": None, "affected_groups": []},
                   route_summary=None)
        try:
            values = resource_object(source["values"], set(COLUMNS["route"]), "input")
            code = resource_text(values.get("business_code"), "business_code")
            typed_value(code, "business_code", row["row"], "csv")
            row["business_code"] = code
            if values["business_code"] != code and values["business_code"] in self.parts:
                raise ValidationError("原图号前后有空格，系统不会当成别的同号零件。请到基础资料改正图号。", field="business_code")
            part = self._resolve(row)
            if not row["errors"]:
                self._propose(row, values, part)
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "input")
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), field="route_raw", code=exc.code)
        return row

    def _resolve(self, row):
        part = self.parts.get(row["business_code"])
        self._check_target(part)
        row["action"] = "create" if part is None else "update"
        if part is not None:
            ref = require_ref(part["ref"], "零件")
            identity = self.identities.get(ref)
            if identity is None or not identity["active"] or identity["kind"] != "part" or identity["entity_key"] != part["part_no"]:
                raise WorkbenchCommandRejected("storage_failure", "零件和它的编号对不上，系统不会替你改资料。请刷新重试；仍不行请联系维护人员。", 500)
            row.update(entity_ref=ref, before=canonical_part(part), reference_count=part["batch_count"],
                       expected={"revision": part["revision"], "part": {
                           key: part[key] for key in ("part_no", "route_raw", "route_parsed")}, "operations": []})
        return part

    def _check_target(self, part):
        if self.target_ref is None:
            return
        target = self.identities.get(self.target_ref) if type(self.target_ref) is str else None
        if target is None or not target["active"] or target["kind"] != "part":
            raise ValidationError("这个零件已失效，不能导入到同号的新零件上。请刷新列表后重新选择。", field="target_ref")
        if part is None or part["ref"] != self.target_ref or target["entity_key"] != part["part_no"]:
            raise ValidationError("详情导入的每一行都必须属于当前零件，不能替换为其他图号。", field="business_code")

    def _propose(self, row, values, part):
        before = row["before"]
        after = self._proposed_fields(row, values, part)
        row.update(input=after, after=after)
        route_changed = after["route_raw"] is not None if part is None else after["route_raw"] != before["route_raw"]
        if route_changed:
            self._route(row, part)
        row["changes"] = {} if before is None else {
            key: {"before": before[key], "after": after[key]} for key in COLUMNS["route"] if before[key] != after[key]}
        row["result"] = "new" if part is None else "update" if row["changes"] else "unchanged"
        row["requires_confirmation"] = bool(route_changed or row["changes"] and row["reference_count"])

    @staticmethod
    def _proposed_fields(row, values, part):
        before = row["before"]
        # The codec omits empty cells. Also keep that contract for direct decoded callers.
        supplied = {key: value for key, value in values.items() if key != "business_code" and value != ""}
        if part is None:
            payload = {"business_code": row["business_code"], **supplied}
            for key, value in supplied.items():
                typed_value(value, key, row["row"], "csv")
            after = WorkbenchProcessPartActionService.normalize_create(payload)
        else:
            after = dict(before)
            for key, value in supplied.items():
                if value == before[key]:
                    continue
                typed_value(value, key, row["row"], "csv")
                if key != "route_raw":
                    if type(value) is str and not value.strip():
                        raise ValidationError("留空格不算清除，要清除请在格子里填 \\N（大写）。", field=key)
                    value = resource_text(value, key, nullable=key == "remark")
                after[key] = value
        return after

    def _check_template(self, code):
        operations, groups = self.operations[code], self.groups[code]
        keys = {row["group_id"] for row in groups}
        for row in operations:
            require_ref(row["ref"], "模板工序")
            if row["status"] not in ("active", "deleted") or type(row["seq"]) is not int or row["seq"] <= 0:
                raise WorkbenchCommandRejected("template_invalid", "原工序的序号或状态无效，系统不会自动恢复或删除。请到基础资料核对工序。", 422)
            if row["ext_group_id"] is not None and row["ext_group_id"] not in keys:
                raise WorkbenchCommandRejected("group_invalid", "原工序关联的外协组不存在，或者属于别的零件。请到基础资料核对外协组。", 422)
        for row in groups:
            require_ref(row["ref"], "模板外协组")
            if type(row["start_seq"]) is not int or type(row["end_seq"]) is not int or not 0 < row["start_seq"] <= row["end_seq"]:
                raise WorkbenchCommandRejected("group_invalid", "原外协组的工序范围无效，算不准影响面。请到基础资料核对外协组起止序。", 422)
        if code in self.foreign_members:
            raise WorkbenchCommandRejected("group_invalid", "这个外协组还被别的零件工序用着，不能在本零件解除。请先到那些零件上解除。", 422)
        return operations, groups

    def _route(self, row, part):
        raw = row["after"]["route_raw"]
        if raw is None:
            raise ValidationError("已有工艺路线不能用 \\N 清除；文件导入不会据此删掉原模板。请到基础资料操作。", field="route_raw")
        if not self.parser_ready:
            self.stack.enter_context(self.parser.reference_snapshot())
            self.parser_ready = True
        preview = self.parser.preview({"mode": "text", "route_raw": raw})
        row["route_summary"] = _route_summary(preview)
        if not preview["can_confirm_route"]:
            raise WorkbenchCommandRejected("route_invalid", "工艺路线无效，这批不能导入。请按下面的逐条提示改好后重新预检。", 422)
        code = row["business_code"]
        operations, groups = self._check_template(code) if part is not None else ([], [])
        affected = affected_group_rows(groups, operations, _changed_sequences(operations, preview))
        row["related"] = {"route": preview, "affected_groups": [{"ref": group["ref"], "group_id": group["group_id"]}
                                                               for group in affected]}
        if part is not None:
            row["expected"]["operations"] = [{key: op[key] for key in ("id", "seq", "status", "op_type_name")}
                                              for op in operations]
        return affected

    def affected_groups(self, rows):
        refs = {group["ref"] for row in rows if row["result"] != "rejected"
                for group in row["related"]["affected_groups"]}
        return [{**project_group(group), "part_ref": self.parts[code]["ref"], "business_code": code}
                for code, groups in self.groups.items() for group in groups if group["ref"] in refs]
