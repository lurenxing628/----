"""Snapshot-only route-file preparation; only parser references need database reads."""

from collections import defaultdict

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_actions import normalize_process_part_create
from core.models.workbench_process_file import COLUMNS
from core.models.workbench_resource_action import action_row, reject_action_row
from core.models.workbench_resource_input import resource_text

from .part_actions_facts import check_process_template
from .projection import project_group, public_sequence, require_ref
from .route_apply import affected_group_rows
from .route_choices import changed_route_sequences, preview_existing_route, route_choice_context
from .route_preview import ProcessRoutePreviewService


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


def _same_template_route(part, existing, preview):
    return (part is not None and part["route_parsed"] == "yes"
            and sorted((op["seq"], op["op_type_name"]) for op in existing if op["status"] == "active")
            == sorted((op["sequence"], op["op_type_name"]) for op in preview["operations"]))


def _route_summary(preview, existing):
    diagnostics = [{**row, **({"sequence": public_sequence(row["sequence"])} if "sequence" in row else {})}
                   for row in preview["diagnostics"]]
    before = {row["seq"]: row["op_type_name"] for row in existing if row["status"] == "active"}
    after = {row["sequence"]: row["op_type_name"] for row in preview["operations"]}
    differences = []
    for sequence in sorted(set(before) | set(after)):
        change = "added" if sequence not in before else "removed" if sequence not in after else \
            "retained" if before[sequence] == after[sequence] else "changed"
        differences.append({"sequence": public_sequence(sequence), "change": change,
                            "before": before.get(sequence), "after": after.get(sequence)})
    return {"counts": dict(preview["counts"]), "diagnostics": diagnostics,
            "can_confirm_route": preview["can_confirm_route"], "differences": differences,
            "operations": [{"sequence": public_sequence(row["sequence"]), "op_type_name": row["op_type_name"],
                            "source_suggestion": row["source_suggestion"], "supplier_label": row["supplier_label"],
                            "external_days": row["external_days"]} for row in preview["operations"]]}


class RouteFilePreview:
    def __init__(self, conn, logger, facts, target_ref, stack):
        self.parts = facts.parts
        self.identities = facts.identities
        self.operations, self.groups = facts.operations, facts.groups
        self.group_parts = facts.group_parts
        self.target_ref, self.stack = target_ref, stack
        self.facts = facts
        self.parser = ProcessRoutePreviewService(conn, logger, facts=facts)
        self.parser_ready = False
        self.choices = {}

    def row(self, source):
        row = action_row(source["row"])
        row.update(errors=list(source["errors"]), related={"route": None, "affected_groups": []},
                   route_summary=None)
        try:
            values = source["values"]
            code = resource_text(values.get("business_code"), "business_code")
            row["business_code"] = code
            if values["business_code"] != code and values["business_code"] in self.parts:
                raise ValidationError("原图号前后有空格。请到基础资料改正图号。", field="business_code")
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
            if identity is None or not identity.active or identity.kind != "part" or identity.entity_key != part["part_no"]:
                raise WorkbenchCommandRejected("storage_failure", "零件和它的编号对不上，请联系维护人员核对资料。", 500)
            row.update(entity_ref=ref, before=canonical_part(part), reference_count=part["batch_count"],
                       expected={"revision": part["revision"], "part": {
                           key: part[key] for key in ("part_no", "route_raw", "route_parsed")}, "operations": []})
        return part

    def _check_target(self, part):
        if self.target_ref is None:
            return
        target = self.identities.get(self.target_ref) if type(self.target_ref) is str else None
        if target is None or not target.active or target.kind != "part":
            raise ValidationError("这个零件已失效，不能导入到同号的新零件上。请刷新列表后重新选择。", field="target_ref")
        if part is None or part["ref"] != self.target_ref or target.entity_key != part["part_no"]:
            raise ValidationError("详情导入的每一行都必须属于当前零件，不能替换为其他图号。", field="business_code")

    def _propose(self, row, values, part):
        before = row["before"]
        after = self._proposed_fields(row, values, part)
        row.update(input=after, after=after)
        route_changed = after["route_raw"] is not None if part is None else after["route_raw"] != before["route_raw"]
        if route_changed:
            self._route(row, part)
            route_changed = row["related"]["route"] is not None
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
            after = normalize_process_part_create(payload)
        else:
            after = dict(before)
            for key, value in supplied.items():
                if value == before[key]:
                    continue
                if key != "route_raw":
                    if type(value) is str and not value.strip():
                        raise ValidationError("留空格不算清除，要清除请在格子里填 \\N（大写）。", field=key)
                    value = resource_text(value, key, nullable=key == "remark")
                after[key] = value
        return after

    def _check_template(self, code):
        operations, groups = self.operations[code], self.groups[code]
        check_process_template(operations, groups, code, self.group_parts)
        return operations, groups

    def _route(self, row, part):
        raw = row["after"]["route_raw"]
        if raw is None:
            raise ValidationError("已有工艺路线不能用 \\N 清除；文件导入不会据此删掉原模板。请到基础资料操作。", field="route_raw")
        code = row["business_code"]
        # 与表单入口同一顺序：先确认原模板的序号、状态和外协组说得清，再拿它比对新路线。
        operations, groups = self._check_template(code) if part is not None else ([], [])
        preview, changed = self._parse_route(raw, operations)
        row["route_summary"] = _route_summary(preview, operations)
        if not preview["can_confirm_route"]:
            raise WorkbenchCommandRejected("route_invalid", "工艺路线无效，这批不能导入。请按下面的逐条提示改好后重新预检。", 422)
        if _same_template_route(part, operations, preview):
            # The readable export may use a different spelling of the same route.
            # Keep existing confirmations and the original stored text on a semantic no-op.
            row["after"]["route_raw"] = row["before"]["route_raw"]
            return []
        if not groups:
            affected = []
        else:
            affected = affected_group_rows(
                groups, operations, {op["sequence"] for op in preview["operations"]} if changed is None else changed)
        row["related"] = {"route": preview, "affected_groups": [{"ref": group["ref"], "group_id": group["group_id"]}
                                                               for group in affected]}
        if part is not None:
            fields = ("id", "seq", "status", "op_type_name", "op_type_id", "source", "supplier_id", "ext_days",
                      "setup_hours", "unit_hours", "ref", "ext_group_id", "part_no")
            row["expected"]["operations"] = [{key: op[key] for key in fields} for op in operations]
        return affected

    def _parse_route(self, raw, existing):
        """Reuse one file-wide reference snapshot and retain explicit choices."""
        if not self.parser_ready:
            self.stack.enter_context(self.parser.reference_snapshot())
            self.parser_ready = True
        preview = self.parser.preview({"mode": "text", "route_raw": raw})
        if not existing:
            return preview, None
        existing_by_seq = {op["seq"]: op for op in existing}
        changed = changed_route_sequences(existing_by_seq, preview["operations"])
        code = existing[0]["part_no"]
        if code not in self.choices:
            self.choices[code] = route_choice_context(existing, self.facts)
        preview = preview_existing_route(preview, existing, self.choices[code], changed=changed)
        return preview, changed

    def affected_groups(self, rows):
        refs = {group["ref"] for row in rows if row["result"] != "rejected"
                for group in row["related"]["affected_groups"]}
        return [{**project_group(group, self.facts.group_members.get(group["group_id"], [])),
                 "part_ref": self.parts[code]["ref"], "business_code": code}
                for code, groups in self.groups.items() for group in groups if group["ref"] in refs]
